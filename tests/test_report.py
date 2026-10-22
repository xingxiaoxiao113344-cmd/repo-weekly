"""Reporting rules that must remain stable independently of the API client."""

import copy
from datetime import timezone
import unittest

from repo_weekly.report import (
    parse_timestamp,
    render_markdown,
    summarize,
    validate_snapshot,
)


def make_snapshot():
    return {
        "schema_version": 1,
        "repository": {
            "full_name": "example/demo-repository",
            "html_url": "https://github.com/example/demo-repository",
            "description": "A fictional test repository.",
        },
        "window": {
            "since": "2026-10-15T00:00:00Z",
            "until": "2026-10-22T00:00:00Z",
        },
        "generated_at": "2026-10-22T00:00:00Z",
        "issues": [],
        "pull_requests": [],
        "releases": [],
        "coverage": {"complete": True, "warnings": []},
    }


def make_issue(number=1, **changes):
    issue = {
        "number": number,
        "title": "Example activity",
        "html_url": f"https://github.com/example/demo-repository/issues/{number}",
        "state": "open",
        "user": {"login": "example-maintainer"},
        "created_at": "2026-10-16T10:00:00Z",
        "updated_at": "2026-10-17T10:00:00Z",
        "closed_at": None,
        "labels": [],
    }
    issue.update(changes)
    return issue


def make_pr(number=2, **changes):
    pull = make_issue(number, **changes)
    pull["html_url"] = f"https://github.com/example/demo-repository/pull/{number}"
    pull.setdefault("merged_at", None)
    return pull


class TimestampTests(unittest.TestCase):
    def test_offset_timestamp_is_normalized_to_utc(self):
        parsed = parse_timestamp("2026-10-15T08:00:00+08:00")
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.isoformat(), "2026-10-15T00:00:00+00:00")

    def test_naive_timestamp_does_not_silently_use_local_timezone(self):
        with self.assertRaises(ValueError):
            parse_timestamp("2026-10-15T00:00:00")


class SnapshotValidationTests(unittest.TestCase):
    def test_valid_empty_snapshot_is_accepted(self):
        validated = validate_snapshot(make_snapshot())
        self.assertEqual(validated["schema_version"], 1)

    def test_unsupported_schema_is_rejected(self):
        snapshot = make_snapshot()
        snapshot["schema_version"] = 999
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot)

    def test_reverse_window_is_rejected(self):
        snapshot = make_snapshot()
        snapshot["window"]["until"] = snapshot["window"]["since"]
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot)

    def test_pull_request_cannot_be_double_counted_as_an_issue(self):
        snapshot = make_snapshot()
        snapshot["issues"] = [make_issue(pull_request={"url": "example"})]
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot)

    def test_invalid_state_cannot_reach_the_markdown_renderer(self):
        for state in ([], {}, None, 1):
            with self.subTest(state=state):
                snapshot = make_snapshot()
                snapshot["issues"] = [make_issue(state=state)]
                with self.assertRaises(ValueError):
                    validate_snapshot(snapshot)


class SummaryTests(unittest.TestCase):
    def test_issue_event_window_is_inclusive_then_exclusive(self):
        snapshot = make_snapshot()
        snapshot["issues"] = [
            make_issue(1, created_at="2026-10-15T00:00:00Z"),
            make_issue(2, created_at="2026-10-22T00:00:00Z"),
            make_issue(
                3,
                created_at="2026-10-01T00:00:00Z",
                closed_at="2026-10-15T00:00:00Z",
                state="closed",
            ),
            make_issue(
                4,
                created_at="2026-10-01T00:00:00Z",
                closed_at="2026-10-22T00:00:00Z",
                state="closed",
            ),
        ]
        result = summarize(snapshot)
        self.assertEqual(result["issues_opened"], 1)
        self.assertEqual(result["issues_closed"], 1)

    def test_merged_pull_request_is_not_closed_unmerged(self):
        snapshot = make_snapshot()
        snapshot["pull_requests"] = [
            make_pr(
                1,
                state="closed",
                merged_at="2026-10-18T12:00:00Z",
                closed_at="2026-10-18T12:00:00Z",
            ),
            make_pr(2, state="closed", closed_at="2026-10-19T12:00:00Z"),
            make_pr(3),
        ]
        result = summarize(snapshot)
        self.assertEqual(result["prs_opened"], 3)
        self.assertEqual(result["prs_merged"], 1)
        self.assertEqual(result["prs_closed_unmerged"], 1)
        self.assertEqual(result["issues_opened"], 0)

    def test_releases_use_publication_time_and_the_same_boundary(self):
        snapshot = make_snapshot()
        snapshot["releases"] = [
            {
                "id": 1,
                "tag_name": "v1.0.0",
                "name": "First version",
                "html_url": "https://github.com/example/demo-repository/releases/tag/v1.0.0",
                "published_at": "2026-10-15T00:00:00Z",
                "draft": False,
                "prerelease": False,
            },
            {
                "id": 2,
                "tag_name": "v1.1.0",
                "name": "Next version",
                "html_url": "https://github.com/example/demo-repository/releases/tag/v1.1.0",
                "published_at": "2026-10-22T00:00:00Z",
                "draft": False,
                "prerelease": False,
            },
        ]
        self.assertEqual(summarize(snapshot)["releases"], 1)

    def test_empty_report_has_zero_counts(self):
        result = summarize(make_snapshot())
        self.assertEqual(set(result), {
            "issues_opened", "issues_closed", "prs_opened", "prs_merged",
            "prs_closed_unmerged", "releases", "active_issues", "active_prs",
        })
        self.assertTrue(all(value == 0 for value in result.values()))


class MarkdownTests(unittest.TestCase):
    def test_html_and_markdown_in_titles_cannot_create_content(self):
        snapshot = make_snapshot()
        snapshot["issues"] = [make_issue(
            title='<script>alert(1)</script> [click](https://evil.example)\n# Injected heading'
        )]
        markdown = render_markdown(snapshot)
        self.assertNotIn("<script>", markdown)
        self.assertNotIn("\n# Injected heading", markdown)
        self.assertNotIn("[click](https://evil.example)", markdown)

    def test_unsafe_source_url_is_not_emitted_as_a_markdown_link(self):
        snapshot = make_snapshot()
        snapshot["issues"] = [make_issue(html_url="javascript:alert(1)")]
        markdown = render_markdown(snapshot)
        self.assertNotIn("](javascript:", markdown)
        self.assertNotIn("<javascript:", markdown)

    def test_incomplete_coverage_warning_is_visible(self):
        snapshot = make_snapshot()
        snapshot["coverage"] = {
            "complete": False,
            "warnings": ["Pull request page limit reached."],
        }
        markdown = render_markdown(snapshot)
        self.assertIn("Pull request page limit reached", markdown)
        self.assertRegex(markdown.lower(), r"partial|incomplete|warning")

    def test_both_languages_keep_counts_and_original_source_titles(self):
        snapshot = make_snapshot()
        snapshot["issues"] = [make_issue(title="Keep the original source title")]
        original = copy.deepcopy(snapshot)
        english = render_markdown(snapshot, lang="en")
        chinese = render_markdown(snapshot, lang="zh")
        self.assertIn("Keep the original source title", english)
        self.assertIn("Keep the original source title", chinese)
        self.assertNotEqual(english, chinese)
        self.assertEqual(snapshot, original)


if __name__ == "__main__":
    unittest.main()
