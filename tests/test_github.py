"""Contract and boundary tests for the read-only GitHub collector."""

import io
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

from repo_weekly.github import GitHubClient, GitHubError, _NoRedirect, parse_repo


SINCE = datetime(2026, 10, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 10, 8, tzinfo=timezone.utc)


def item(number, **overrides):
    result = {"id": number, "number": number, "created_at": "2026-10-02T00:00:00Z", "updated_at": "2026-10-03T00:00:00Z", "closed_at": None}
    result.update(overrides)
    return result


class RepositoryParsingTests(unittest.TestCase):
    def test_supported_input_forms(self):
        for value in ("owner/repo", "owner/repo.git", "https://github.com/owner/repo/", "https://github.com/owner/repo.git/"):
            with self.subTest(value=value):
                self.assertEqual(parse_repo(value), "owner/repo")

    def test_rejects_noncanonical_and_unsafe_names(self):
        for value in ("", " owner/repo", "owner/repo/issues", "https://evil.example/owner/repo", "http://github.com/owner/repo", "https://github.com@evil.example/owner/repo", "https://github.com/owner/repo?secret=x", "https://[bad/owner/repo", "owner/..", "owner/repo\n", "owner/repo%2fmore"):
            with self.subTest(value=value), self.assertRaises(GitHubError):
                parse_repo(value)


class RequestTests(unittest.TestCase):
    def test_only_fixed_https_host_is_allowed(self):
        client = GitHubClient(token="secret-token")
        for path in ("https://evil.example/user", "//evil.example/user", "http://api.github.com/user", "https://api.github.com:443/user", "https://api.github.com@evil.example/user", "https://[bad/user", "https://api.github.com/user#fragment", "/user\n", "/\\evil.example"):
            with self.subTest(path=path), self.assertRaises(GitHubError):
                client.get(path)

    def test_parameters_are_encoded_and_get_is_used(self):
        client = GitHubClient(token="secret-token")
        response = MagicMock()
        response.headers = {"Content-Type": "application/json"}
        response.read.return_value = b'{"ok": true}'
        client._opener.open = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=response), __exit__=MagicMock(return_value=False)))
        self.assertEqual(client.get("/search/issues", {"q": "repo:owner/repo label:help wanted"}), {"ok": True})
        request = client._opener.open.call_args.args[0]
        self.assertEqual(request.method, "GET")
        self.assertIn("q=repo%3Aowner%2Frepo", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")

    def test_redirects_disabled(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example"))

    def test_rate_limit_is_actionable_and_never_echoes_body_or_token(self):
        client = GitHubClient(token="secret-token")
        client._opener.open = MagicMock(side_effect=HTTPError("https://api.github.com/user", 403, "secret-token", {"X-RateLimit-Remaining": "0", "Retry-After": "120"}, io.BytesIO(b'secret-token')))
        with self.assertRaises(GitHubError) as caught:
            client.get("/user")
        self.assertIn("rate limit", str(caught.exception))
        self.assertIn("120 seconds", str(caught.exception))
        self.assertNotIn("secret-token", str(caught.exception))

    def test_other_errors_are_not_silently_empty(self):
        client = GitHubClient()
        for error in (HTTPError("https://api.github.com/user", 401, "bad", {}, io.BytesIO()), HTTPError("https://api.github.com/user", 301, "moved", {}, io.BytesIO()), URLError("sensitive diagnostic")):
            client._opener.open = MagicMock(side_effect=error)
            with self.subTest(error=error), self.assertRaises(GitHubError):
                client.get("/user")

    def test_configuration_validation(self):
        for kwargs in ({"max_pages": 0}, {"max_pages": True}, {"timeout": 0}, {"timeout": float("nan")}, {"token": "bad\nvalue"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(GitHubError):
                GitHubClient(**kwargs)


class CollectionTests(unittest.TestCase):
    def client(self, responses, max_pages=10):
        client = GitHubClient(max_pages=max_pages)
        client._request = MagicMock(side_effect=[({"full_name": "owner/repo", "html_url": "https://github.com/owner/repo", "description": None}, {})] + responses)
        return client

    def test_prs_not_double_counted_and_upper_bound_exclusive(self):
        client = self.client([
            ([item(1), item(2, pull_request={}), item(3, created_at="2026-10-08T00:00:00Z", updated_at="2026-10-08T00:00:00Z")], {}),
            ([item(2, merged_at="2026-10-04T00:00:00Z"), item(2, merged_at="2026-10-04T00:00:00Z")], {}),
            ([{"id": 10, "published_at": "2026-10-02T00:00:00Z", "draft": False}, {"id": 11, "published_at": "2026-10-03T00:00:00Z", "draft": True}], {}),
        ])
        result = client.collect("owner/repo", SINCE, UNTIL)
        self.assertEqual([row["number"] for row in result["issues"]], [1])
        self.assertEqual([row["number"] for row in result["pull_requests"]], [2])
        self.assertEqual([row["id"] for row in result["releases"]], [10])
        self.assertTrue(result["coverage"]["complete"])
        self.assertEqual(result["window"]["until"], "2026-10-08T00:00:00Z")

    def test_event_in_window_survives_later_update(self):
        client = self.client([([item(1, updated_at="2026-10-15T00:00:00Z")], {}), ([], {}), ([], {})])
        self.assertEqual(len(client.collect("owner/repo", SINCE, UNTIL)["issues"]), 1)

    def test_issue_fetch_includes_exact_start_without_earlier_items(self):
        client = self.client([
            ([item(1, created_at="2026-10-01T00:00:00Z", updated_at="2026-10-01T00:00:00Z"),
              item(2, created_at="2026-09-30T23:59:59Z", updated_at="2026-09-30T23:59:59Z")], {}),
            ([], {}), ([], {}),
        ])
        result = client.collect("owner/repo", SINCE, UNTIL)
        self.assertEqual([row["number"] for row in result["issues"]], [1])
        self.assertEqual(client._request.call_args_list[1].args[1]["since"], "2026-09-30T23:59:59Z")

    def test_snapshot_preserves_microsecond_boundaries(self):
        since = SINCE.replace(microsecond=123456)
        until = UNTIL.replace(microsecond=654321)
        client = self.client([
            ([item(1, created_at="2026-10-01T00:00:00.123456Z", updated_at="2026-10-01T00:00:00.123456Z"),
              item(2, created_at="2026-10-01T00:00:00.123455Z", updated_at="2026-10-01T00:00:00.123455Z"),
              item(3, created_at="2026-10-08T00:00:00.654321Z", updated_at="2026-10-08T00:00:00.654321Z")], {}),
            ([], {}), ([], {}),
        ])
        result = client.collect("owner/repo", since, until)
        self.assertEqual(result["window"], {"since": "2026-10-01T00:00:00.123456Z", "until": "2026-10-08T00:00:00.654321Z"})
        self.assertEqual([row["number"] for row in result["issues"]], [1])
        self.assertEqual(client._request.call_args_list[1].args[1]["since"], "2026-09-30T23:59:59.123456Z")

    def test_follows_next_and_marks_only_real_page_limit(self):
        next_header = {"link": '<https://api.github.com/repos/owner/repo/issues?page=2>; rel="next"'}
        client = self.client([([item(1)], next_header), ([], {}), ([], {})], max_pages=1)
        result = client.collect("owner/repo", SINCE, UNTIL)
        self.assertFalse(result["coverage"]["complete"])
        self.assertIn("issues", result["coverage"]["warnings"][0])
        client = self.client([([item(1)], next_header), ([item(2)], {}), ([], {}), ([], {})])
        result = client.collect("owner/repo", SINCE, UNTIL)
        self.assertEqual(len(result["issues"]), 2)
        self.assertTrue(result["coverage"]["complete"])

    def test_old_pull_page_stops_without_false_truncation(self):
        old = item(2, created_at="2020-01-01T00:00:00Z", updated_at="2020-01-01T00:00:00Z")
        client = self.client([( [], {}), ([old], {"link": '<https://api.github.com/repos/owner/repo/pulls?page=2>; rel="next"'}), ([], {})], max_pages=1)
        result = client.collect("owner/repo", SINCE, UNTIL)
        self.assertTrue(result["coverage"]["complete"])
        self.assertEqual(result["pull_requests"], [])

    def test_release_order_does_not_skip_later_pages(self):
        client = self.client([( [], {}), ([], {}), ([{"id": 1, "published_at": "2020-01-01T00:00:00Z"}], {"link": '<https://api.github.com/repos/owner/repo/releases?page=2>; rel="next"'}), ([{"id": 2, "published_at": "2026-10-03T00:00:00Z"}], {})])
        self.assertEqual([row["id"] for row in client.collect("owner/repo", SINCE, UNTIL)["releases"]], [2])

    def test_invalid_boundaries_and_payload(self):
        client = GitHubClient()
        with self.assertRaises(GitHubError):
            client.collect("owner/repo", UNTIL, SINCE)
        with self.assertRaises(GitHubError):
            client.collect("owner/repo", datetime(2026, 1, 1), UNTIL)
        client = self.client([({"error": "unexpected"}, {})])
        with self.assertRaises(GitHubError):
            client.collect("owner/repo", SINCE, UNTIL)

    def test_discovery_limit_and_page_limit_are_explicit(self):
        client = GitHubClient(max_pages=1)
        client._request = MagicMock(return_value=([{"full_name": "owner/a"}], {"link": '<https://api.github.com/users/owner/repos?page=2>; rel="next"'}))
        self.assertEqual(len(client.repos("owner", 1)), 1)
        with self.assertRaises(GitHubError):
            client.repos("owner", 2)


if __name__ == "__main__":
    unittest.main()
