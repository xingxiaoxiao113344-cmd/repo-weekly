"""Validate snapshots and render reports without contacting a model or service."""

from __future__ import annotations

from datetime import datetime, timezone
import html
import re
from urllib.parse import quote, urlsplit


def parse_timestamp(value: str) -> datetime:
    """Parse a timezone-aware ISO timestamp, normalizing it to UTC."""
    if not isinstance(value, str):
        raise ValueError("Timestamps must be ISO 8601 strings with a timezone.")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value!r}") from exc
    if result.tzinfo is None:
        raise ValueError("Timestamps must include a timezone (for example, Z).")
    return result.astimezone(timezone.utc)


def validate_snapshot(snapshot: dict) -> dict:
    """Reject incomplete or ambiguous inputs instead of reporting false zeroes."""
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise ValueError("Expected a snapshot with schema_version: 1.")
    repo = snapshot.get("repository")
    if not isinstance(repo, dict) or not isinstance(repo.get("full_name"), str):
        raise ValueError("Snapshot is missing repository.full_name.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo["full_name"]):
        raise ValueError("repository.full_name must be OWNER/REPO.")
    window = snapshot.get("window")
    if not isinstance(window, dict):
        raise ValueError("Snapshot is missing window.")
    since = parse_timestamp(window.get("since"))
    until = parse_timestamp(window.get("until"))
    if since >= until:
        raise ValueError("window.since must be earlier than window.until.")
    parse_timestamp(snapshot.get("generated_at"))
    coverage = snapshot.get("coverage")
    if not isinstance(coverage, dict) or type(coverage.get("complete")) is not bool:
        raise ValueError("Snapshot needs coverage.complete (true or false).")
    if not isinstance(coverage.get("warnings"), list) or not all(
        isinstance(warning, str) for warning in coverage["warnings"]
    ):
        raise ValueError("coverage.warnings must be a list of strings.")
    for category in ("issues", "pull_requests", "releases"):
        items = snapshot.get(category)
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise ValueError(f"{category} must be a list of objects.")
        for item in items:
            if not isinstance(item.get("title", item.get("name", "")), (str, type(None))):
                raise ValueError(f"{category} contains an invalid title.")
            if category == "issues" and "pull_request" in item:
                raise ValueError("issues must not contain pull requests; use pull_requests.")
            if category != "releases" and item.get("state") not in ("open", "closed"):
                raise ValueError(f"{category} items need state: open or closed.")
            required = "published_at" if category == "releases" else "created_at"
            if not item.get(required):
                raise ValueError(f"{category} contains an item without {required}.")
            for field in ("created_at", "updated_at", "closed_at", "merged_at", "published_at"):
                if item.get(field) is not None:
                    parse_timestamp(item[field])
    return snapshot


def _inside(value: str | None, since: datetime, until: datetime) -> bool:
    return bool(value) and since <= parse_timestamp(value) < until


def _activity(item: dict, category: str, since: datetime, until: datetime) -> list[datetime]:
    fields = ("published_at",) if category == "releases" else (
        "created_at", "updated_at", "closed_at", "merged_at"
    )
    return [parse_timestamp(item[field]) for field in fields if _inside(item.get(field), since, until)]


def _window_items(snapshot: dict, category: str) -> list[dict]:
    since = parse_timestamp(snapshot["window"]["since"])
    until = parse_timestamp(snapshot["window"]["until"])
    selected = [item for item in snapshot[category] if _activity(item, category, since, until)]
    return sorted(selected, key=lambda item: max(_activity(item, category, since, until)), reverse=True)


def summarize(snapshot: dict) -> dict[str, int]:
    validate_snapshot(snapshot)
    since = parse_timestamp(snapshot["window"]["since"])
    until = parse_timestamp(snapshot["window"]["until"])
    issues = _window_items(snapshot, "issues")
    prs = _window_items(snapshot, "pull_requests")
    return {
        "issues_opened": sum(_inside(i.get("created_at"), since, until) for i in issues),
        "issues_closed": sum(_inside(i.get("closed_at"), since, until) for i in issues),
        "prs_opened": sum(_inside(p.get("created_at"), since, until) for p in prs),
        "prs_merged": sum(_inside(p.get("merged_at"), since, until) for p in prs),
        "prs_closed_unmerged": sum(
            _inside(p.get("closed_at"), since, until) and not p.get("merged_at") for p in prs
        ),
        "releases": len(_window_items(snapshot, "releases")),
        "active_issues": len(issues),
        "active_prs": len(prs),
    }


def _text(value: object) -> str:
    """Keep remote titles as single-line text, including in Markdown tables."""
    text = " ".join(str(value or "").split())
    text = "".join(c for c in text if ord(c) >= 32 and not 0x202A <= ord(c) <= 0x202E)
    text = html.escape(text, quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+.!|~])", r"\\\1", text)


def _link(label: str, url: object) -> str:
    label = _text(label)
    if not isinstance(url, str):
        return label
    try:
        parts = urlsplit(url)
        safe = (
            parts.scheme == "https" and parts.netloc == "github.com"
            and not parts.username and not parts.password and "\\" not in url
            and not any(ord(c) < 33 for c in url)
        )
    except ValueError:
        safe = False
    if not safe:
        return label
    return f"[{label}]({quote(url, safe=':/?=&%#@+,-._~')})"


_EN = {
    "title": "Weekly maintenance report", "window": "Activity window (UTC)",
    "generated": "Snapshot generated", "summary": "Summary", "metric": "Metric", "count": "Count",
    "issues_opened": "Issues opened", "issues_closed": "Issues closed",
    "prs_opened": "Pull requests opened", "prs_merged": "Pull requests merged",
    "prs_closed_unmerged": "Pull requests closed without merge", "releases": "Releases published",
    "active_issues": "Issues with activity", "active_prs": "Pull requests with activity",
    "issues": "Issues with activity", "pull_requests": "Pull requests with activity",
    "release_heading": "Published releases", "empty": "No matching activity in this window.",
    "state": "current state", "author": "author", "updated": "updated", "published": "published",
    "merged": "merged", "open": "open", "closed": "closed", "draft": "draft",
    "partial": "PARTIAL DATA: a collection limit was reached. Counts are lower bounds.",
    "complete": "All API pages required by this collection were read.",
    "shown": "Showing {shown} of {total}; the JSON snapshot retains all collected records.",
    "notes": "How to read this report",
    "scope": "This is a snapshot of current GitHub records, not a complete event history. Reopened issues, previous states, and deleted records cannot be reconstructed. Counts use the timestamps currently returned by GitHub.",
    "language": "Headings and labels are localized; original issue, PR, and release titles are preserved. No AI summary or translation is performed.",
    "window_note": "The window includes its start and excludes its end. Issue and pull request counts are separate; merged PRs are excluded from closed-without-merge counts.",
    "demo": "DEMO: this report uses fictional repository activity, not real usage or adoption evidence.",
}
_ZH = {
    "title": "维护周报", "window": "活动时间范围（UTC）", "generated": "快照生成时间",
    "summary": "概览", "metric": "指标", "count": "数量",
    "issues_opened": "新建 Issue", "issues_closed": "关闭 Issue",
    "prs_opened": "新建 PR", "prs_merged": "合并 PR", "prs_closed_unmerged": "未合并即关闭 PR",
    "releases": "发布版本", "active_issues": "有活动的 Issue", "active_prs": "有活动的 PR",
    "issues": "有活动的 Issue", "pull_requests": "有活动的 PR", "release_heading": "发布的版本",
    "empty": "该时间范围内没有匹配的活动。", "state": "当前状态", "author": "作者",
    "updated": "更新时间", "published": "发布时间", "merged": "已合并", "open": "打开",
    "closed": "关闭", "draft": "草稿", "partial": "数据不完整：采集触及分页上限，以下计数是已采集记录的下限。",
    "complete": "本次采集所需的 API 页面已读取完毕。",
    "shown": "展示 {shown} / {total} 条；JSON 快照保留全部已采集记录。",
    "notes": "阅读说明",
    "scope": "本报告基于 GitHub 当前记录快照，并非完整事件历史。无法还原重复打开、以前的状态或已删除的记录；计数使用 GitHub 当前返回的时间戳。",
    "language": "仅标题和标签切换语言，保留 Issue、PR 和版本的原始标题；本版本不进行 AI 摘要或翻译。",
    "window_note": "时间范围包含起点、不包含终点。Issue 和 PR 分开统计，合并 PR 不计入“未合并即关闭 PR”。",
    "demo": "演示：本报告使用虚构的仓库活动，不代表真实用户、使用量或项目影响力。",
}


def render_markdown(snapshot: dict, lang: str = "en", max_items: int = 20) -> str:
    if lang not in ("en", "zh"):
        raise ValueError("lang must be en or zh.")
    if type(max_items) is not int or max_items < 1:
        raise ValueError("max_items must be a positive integer.")
    summary = summarize(snapshot)
    labels = _ZH if lang == "zh" else _EN
    repo = snapshot["repository"]
    lines = [f"# {_link(repo['full_name'], repo.get('html_url'))} · {labels['title']}", ""]
    if snapshot.get("fixture") is True:
        lines.extend([f"> {labels['demo']}", ""])
    stamp = lambda value: parse_timestamp(value).isoformat().replace("+00:00", "Z")
    lines.extend([
        f"{labels['window']}: `{stamp(snapshot['window']['since'])}` ≤ activity < `{stamp(snapshot['window']['until'])}`",
        "", f"{labels['generated']}: `{stamp(snapshot['generated_at'])}`", "",
    ])
    if not snapshot["coverage"]["complete"]:
        lines.extend([f"> **{labels['partial']}**", ""])
    for warning in snapshot["coverage"]["warnings"]:
        lines.extend([f"> {_text(warning)}", ""])
    lines.extend([f"## {labels['summary']}", "", f"| {labels['metric']} | {labels['count']} |", "| --- | ---: |"])
    lines.extend(f"| {labels[key]} | {count} |" for key, count in summary.items())
    lines.append("")
    for category in ("issues", "pull_requests", "releases"):
        items = _window_items(snapshot, category)
        heading = labels["release_heading"] if category == "releases" else labels[category]
        lines.extend([f"## {heading}", ""])
        if not items:
            lines.extend([labels["empty"], ""])
            continue
        if len(items) > max_items:
            lines.extend([labels["shown"].format(shown=max_items, total=len(items)), ""])
        for item in items[:max_items]:
            if category == "releases":
                title = item.get("name") or item.get("tag_name") or "Release"
                detail = f"{labels['published']}: {_text(item['published_at'])}"
            else:
                title = f"#{item.get('number', '?')} {item.get('title', '')}"
                state = "merged" if item.get("merged_at") else item.get("state", "unknown")
                user = item.get("user") or {}
                user = user.get("login", "unknown") if isinstance(user, dict) else "unknown"
                detail = f"{labels['state']}: {_text(labels.get(state, state))}; {labels['author']}: @{_text(user)}"
                if item.get("draft"):
                    detail += f"; {labels['draft']}"
                if item.get("updated_at"):
                    detail += f"; {labels['updated']}: {_text(item['updated_at'])}"
            lines.append(f"- {_link(title, item.get('html_url'))} — {detail}")
        lines.append("")
    lines.extend([
        f"## {labels['notes']}", "", labels["scope"], "", labels["window_note"], "", labels["language"], "",
    ])
    if snapshot["coverage"]["complete"]:
        lines.extend([labels["complete"], ""])
    return "\n".join(lines)
