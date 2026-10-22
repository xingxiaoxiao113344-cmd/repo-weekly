"""Read-only GitHub REST client with bounded, explicit collection coverage."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_URL = "https://api.github.com"
API_VERSION = "2022-11-28"
_OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
_MAX_RESPONSE_BYTES = 20 * 1024 * 1024


class GitHubError(Exception):
    """An actionable input, transport, or GitHub API failure."""


def parse_repo(value: str) -> str:
    """Normalize OWNER/REPO or a canonical HTTPS GitHub repository URL."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise GitHubError("Repository must be OWNER/REPO or an HTTPS GitHub repository URL.")
    if "://" in value:
        try:
            parsed = urlsplit(value)
        except ValueError:
            raise GitHubError("Repository URL is malformed.") from None
        if (
            parsed.scheme != "https"
            or parsed.netloc.lower() != "github.com"
            or parsed.query
            or parsed.fragment
        ):
            raise GitHubError("Repository URLs must use https://github.com/OWNER/REPO.")
        value = parsed.path.removeprefix("/").removesuffix("/")
    else:
        value = value.removesuffix("/")
    value = value.removesuffix(".git")
    pieces = value.split("/")
    if (
        len(pieces) != 2
        or not _OWNER.fullmatch(pieces[0])
        or not _REPO.fullmatch(pieces[1])
        or pieces[1] in {".", ".."}
    ):
        raise GitHubError("Repository must be OWNER/REPO with a valid GitHub owner and name.")
    return "/".join(pieces)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise GitHubError("Collection boundaries must be timezone-aware datetimes.")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise GitHubError("GitHub returned an invalid timestamp.")
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, OverflowError) as exc:
        raise GitHubError("GitHub returned an invalid timestamp.") from exc


def _active(item: dict[str, Any], since: datetime, until: datetime) -> bool:
    return any(
        stamp is not None and since <= stamp < until
        for stamp in (
            _timestamp(item.get(field))
            for field in ("created_at", "updated_at", "closed_at", "merged_at")
        )
    )


def _deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, Any]] = set()
    for item in items:
        key = next(((field, item[field]) for field in ("id", "number", "html_url") if item.get(field) is not None), None)
        if key is None or key not in seen:
            result.append(item)
            if key is not None:
                seen.add(key)
    return result


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubClient:
    """Only send authenticated GET requests to api.github.com over HTTPS."""

    def __init__(self, token: str | None = None, timeout: float = 30, max_pages: int = 10):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise GitHubError("Timeout must be a positive finite number of seconds.")
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 1000:
            raise GitHubError("max_pages must be an integer from 1 to 1000.")
        if token is not None and (not isinstance(token, str) or any(c.isspace() for c in token)):
            raise GitHubError("GITHUB_TOKEN must contain a token without whitespace.")
        self.token = token or None
        self.timeout = timeout
        self.max_pages = max_pages
        self._opener = build_opener(_NoRedirect())

    @staticmethod
    def _url(path: str, params: dict[str, Any] | None = None) -> str:
        if not isinstance(path, str) or not path or any(ord(c) <= 32 or ord(c) == 127 for c in path) or "\\" in path:
            raise GitHubError("API paths must not contain whitespace, control characters, or backslashes.")
        try:
            parsed = urlsplit(path)
        except ValueError:
            raise GitHubError("API URL is malformed.") from None
        if parsed.scheme or parsed.netloc:
            if parsed.scheme != "https" or parsed.netloc.lower() != "api.github.com":
                raise GitHubError("API requests must target https://api.github.com only.")
        elif not path.startswith("/") or path.startswith("//"):
            raise GitHubError("Use an API path beginning with /, such as /rate_limit.")
        if parsed.fragment:
            raise GitHubError("API paths must not contain URL fragments.")
        query = parsed.query
        if params:
            query = "&".join(part for part in (query, urlencode(params, doseq=True)) if part)
        return urlunsplit(("https", "api.github.com", parsed.path or "/", query, ""))

    def _request(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, dict[str, str]]:
        url = self._url(path, params)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "repo-weekly/0.1.0",
            "X-GitHub-Api-Version": API_VERSION,
        }
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(url, headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                response_headers = {key.lower(): value for key, value in response.headers.items()}
                body = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            status = exc.code
            response_headers = {key.lower(): value for key, value in exc.headers.items()} if exc.headers else {}
            exc.close()
            if status in {403, 429} and (
                status == 429
                or response_headers.get("x-ratelimit-remaining") == "0"
                or "retry-after" in response_headers
            ):
                hint = "GitHub rate limit reached. Wait before retrying; use GITHUB_TOKEN for authenticated access."
                retry = response_headers.get("retry-after", "")
                reset = response_headers.get("x-ratelimit-reset", "")
                if retry.isdigit():
                    hint += f" Retry after {retry} seconds."
                elif reset.isdigit():
                    hint += f" Rate limit resets at Unix timestamp {reset}."
                raise GitHubError(hint) from None
            messages = {
                401: "GitHub authentication failed. Check GITHUB_TOKEN or unset it for public access.",
                403: "GitHub denied access or applied a secondary rate limit. Check token permissions and wait before retrying.",
                404: "GitHub resource not found. Check its name and token access.",
                410: "GitHub no longer supports the requested API version or resource.",
                422: "GitHub rejected the request parameters.",
            }
            if 300 <= status < 400:
                message = "GitHub redirected the request. Use the repository's current canonical name; redirects are disabled."
            else:
                message = messages.get(status, f"GitHub request failed with HTTP {status}.")
            raise GitHubError(message) from None
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise GitHubError("Could not reach GitHub. Check your connection, proxy, and timeout, then retry.") from None
        if len(body) > _MAX_RESPONSE_BYTES:
            raise GitHubError("GitHub response exceeded the 20 MiB safety limit; use a narrower request.")
        try:
            return json.loads(body), response_headers
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GitHubError("GitHub returned an invalid JSON response.") from None

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Read one API response. No write methods are supported."""
        return self._request(path, params)[0]

    def repo(self, value: str) -> dict[str, Any]:
        data = self.get("/repos/" + parse_repo(value))
        if not isinstance(data, dict) or not isinstance(data.get("full_name"), str):
            raise GitHubError("GitHub returned invalid repository metadata.")
        return data

    @staticmethod
    def _next(headers: dict[str, str]) -> str | None:
        match = re.search(r'<([^>]+)>\s*;\s*rel="next"', headers.get("link", ""))
        return match.group(1) if match else None

    def _pages(self, path: str, params: dict[str, Any], label: str, warnings: list[str], stop_before: datetime | None = None):
        current: str | None = path
        query: dict[str, Any] | None = {**params, "per_page": 100, "page": 1}
        for page_number in range(1, self.max_pages + 1):
            data, headers = self._request(current, query)
            if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
                raise GitHubError(f"GitHub returned invalid {label} data.")
            yield from data
            if stop_before is not None and data:
                last_updated = _timestamp(data[-1].get("updated_at"))
                if last_updated is not None and last_updated < stop_before:
                    return
            current = self._next(headers)
            if not current:
                return
            if page_number == self.max_pages:
                warnings.append(f"{label}: reached --max-pages={self.max_pages}; more pages remain and this source is incomplete.")
                return
            query = None

    def repos(self, owner: str, limit: int = 20) -> list[dict[str, Any]]:
        """Discover a bounded list of public repositories for an owner."""
        if not isinstance(owner, str) or not _OWNER.fullmatch(owner):
            raise GitHubError("Owner must be a GitHub user or organization name.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise GitHubError("Repository limit must be an integer from 1 to 1000.")
        current = f"/users/{owner}/repos"
        params: dict[str, Any] | None = {"type": "owner", "sort": "updated", "per_page": min(limit, 100), "page": 1}
        result: list[dict[str, Any]] = []
        for _ in range(self.max_pages):
            data, headers = self._request(current, params)
            if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
                raise GitHubError("GitHub returned invalid repository discovery data.")
            result.extend(data)
            next_url = self._next(headers)
            if len(result) >= limit or not next_url:
                return result[:limit]
            current, params = next_url, None
        raise GitHubError("Repository discovery reached --max-pages before the requested limit; increase it or lower --limit.")

    def collect(self, repository: str, since: datetime, until: datetime) -> dict[str, Any]:
        """Collect current API objects relevant to a half-open UTC time window."""
        since, until = _utc(since), _utc(until)
        if since >= until:
            raise GitHubError("The collection start must precede its end.")
        metadata = self.repo(repository)
        name = parse_repo(metadata["full_name"])
        root = "/repos/" + name
        warnings: list[str] = []
        # GitHub's since filter is strictly "updated after". Fetch slightly
        # before our inclusive lower bound, then enforce the exact window here.
        issue_since = since - timedelta(seconds=1)
        issues = [item for item in self._pages(root + "/issues", {"state": "all", "since": _iso(issue_since), "sort": "updated", "direction": "desc"}, "issues", warnings)
                  if "pull_request" not in item and _active(item, since, until)]
        pulls = [item for item in self._pages(root + "/pulls", {"state": "all", "sort": "updated", "direction": "desc"}, "pull_requests", warnings, stop_before=since)
                 if _active(item, since, until)]
        releases = []
        for item in self._pages(root + "/releases", {}, "releases", warnings):
            published = _timestamp(item.get("published_at"))
            if not item.get("draft") and published is not None and since <= published < until:
                releases.append(item)
        return {
            "schema_version": 1,
            "repository": {"full_name": name, "html_url": metadata.get("html_url", "https://github.com/" + name), "description": metadata.get("description")},
            "window": {"since": _iso(since), "until": _iso(until)},
            "generated_at": _iso(datetime.now(timezone.utc)),
            "issues": _deduplicate(issues),
            "pull_requests": _deduplicate(pulls),
            "releases": _deduplicate(releases),
            "coverage": {"complete": not warnings, "warnings": warnings},
        }
