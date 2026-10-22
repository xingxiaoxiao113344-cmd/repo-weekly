"""Command-line entry point. Network commands only read the GitHub REST API."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from importlib.resources import files
import json
import os
from pathlib import Path
import sys

from . import __version__
from .github import GitHubClient, GitHubError, parse_repo
from .report import parse_timestamp, render_markdown, summarize, validate_snapshot


class CLIError(Exception):
    def __init__(self, message: str, code: str = "invalid_input", status: int = 2):
        super().__init__(message)
        self.code, self.status = code, status


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CLIError(message)


def _integer(low: int, high: int):
    def convert(value: str) -> int:
        try:
            result = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("expected an integer") from exc
        if not low <= result <= high:
            raise argparse.ArgumentTypeError(f"expected a value from {low} to {high}")
        return result
    return convert


def _parser() -> Parser:
    parser = Parser(prog="repo-weekly", description="Generate source-linked GitHub maintenance reports in English or Chinese.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--json", action="store_true", help="emit a stable JSON envelope (also accepted after a command)")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="check installation, fixture and auth; network is opt-in")
    mode = doctor.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="verify fixture mode without network")
    mode.add_argument("--check-network", action="store_true", help="read GitHub API rate-limit information")
    repo = commands.add_parser("repo", help="resolve a GitHub repository name or URL to metadata")
    repo.add_argument("repository")
    repos = commands.add_parser("repos", help="discover public repositories owned by a user or organization")
    repos.add_argument("owner")
    repos.add_argument("--limit", type=_integer(1, 100), default=20)
    for name, help_text in (("collect", "download an activity snapshot as JSON"), ("report", "render a Markdown maintenance report")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("repository", help="OWNER/REPO or https://github.com/OWNER/REPO")
        command.add_argument("--days", type=_integer(1, 365), default=None, help="window length; default: 7 days")
        command.add_argument("--until", help="exclusive window end: YYYY-MM-DD (00:00 UTC) or timezone-aware ISO timestamp")
        command.add_argument("--max-pages", type=_integer(1, 100), default=10, help="page cap per API source; default: 10")
        command.add_argument("--output", type=Path, help="save to a UTF-8 file")
        command.add_argument("--force", action="store_true", help="allow replacing an existing output file")
        if name == "report":
            command.add_argument("--lang", choices=("en", "zh"), default="en", help="heading and label language; original titles are preserved")
            command.add_argument("--max-items", type=_integer(1, 500), default=20, help="display cap per section; counts retain all collected items")
            command.add_argument("--data", type=Path, help="read a saved snapshot offline, using its saved time window")
    demo = commands.add_parser("demo", help="generate a report using packaged fictional data, offline")
    demo.add_argument("--lang", choices=("en", "zh"), default="en")
    demo.add_argument("--max-items", type=_integer(1, 500), default=20)
    demo.add_argument("--output", type=Path)
    demo.add_argument("--force", action="store_true")
    api = commands.add_parser("api", help="raw read-only GET against api.github.com (no external hosts)")
    api.add_argument("path", help="relative GitHub API path, including an optional query")
    return parser


def _token() -> tuple[str | None, str]:
    for variable in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(variable, "").strip()
        if token:
            return token, variable
    return None, "missing"


def _demo() -> dict:
    return validate_snapshot(json.loads(files("repo_weekly").joinpath("data/demo.json").read_text(encoding="utf-8")))


def _load(path: Path) -> dict:
    if path.stat().st_size > 30_000_000:
        raise CLIError("Snapshot exceeds the 30 MB input limit.")
    return validate_snapshot(json.loads(path.read_text(encoding="utf-8-sig")))


def _save(path: Path | None, content: str, force: bool) -> str | None:
    if path is None:
        return None
    try:
        # Exclusive creation prevents an accidental overwrite, including a race.
        with path.open("w" if force else "x", encoding="utf-8", newline="\n") as target:
            target.write(content)
    except FileExistsError as exc:
        raise CLIError(f"Output already exists: {path}. Choose another path or use --force.", "output_exists", 1) from exc
    return str(path.resolve())


def _window(args) -> tuple[datetime, datetime]:
    if args.until:
        value = args.until
        if len(value) == 10:
            value += "T00:00:00Z"
        until = parse_timestamp(value)
    else:
        until = datetime.now(timezone.utc).replace(microsecond=0)
    return until - timedelta(days=args.days or 7), until


def _execute(args) -> tuple[object, str, int]:
    token, auth_source = _token()
    if args.command == "doctor":
        fixture = _demo()
        data = {
            "version": __version__, "python_version": sys.version.split()[0],
            "auth_available": bool(token), "auth_source": auth_source,
            "offline": args.offline, "auth_required": False,
            "fixture_available": bool(fixture), "network_checked": args.check_network,
        }
        if args.check_network:
            data["rate_limit"] = GitHubClient(token=token).get("/rate_limit").get("rate", {})
        return data, json.dumps(data, ensure_ascii=False, indent=2), 0
    if args.command == "demo":
        snapshot = _demo()
    elif args.command in ("collect", "report"):
        repository = parse_repo(args.repository)
        if args.command == "report" and args.data:
            if args.days is not None or args.until is not None:
                raise CLIError("--data uses the snapshot window; omit --days and --until.")
            snapshot = _load(args.data)
            if snapshot["repository"]["full_name"].lower() != repository.lower():
                raise CLIError("The snapshot repository does not match the requested repository.")
        else:
            since, until = _window(args)
            snapshot = validate_snapshot(GitHubClient(token=token, max_pages=args.max_pages).collect(repository, since, until))
        if args.command == "collect":
            content = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
            output = _save(args.output, content, args.force)
            data = {"snapshot": snapshot, "output": output}
            return data, f"Saved snapshot: {output}" if output else content.rstrip(), 0 if snapshot["coverage"]["complete"] else 3
    elif args.command == "repo":
        data = GitHubClient(token=token).repo(parse_repo(args.repository))
        return data, json.dumps(data, ensure_ascii=False, indent=2), 0
    elif args.command == "repos":
        data = GitHubClient(token=token).repos(args.owner, limit=args.limit)
        return data, json.dumps(data, ensure_ascii=False, indent=2), 0
    else:
        data = GitHubClient(token=token).get(args.path)
        return data, json.dumps(data, ensure_ascii=False, indent=2), 0
    markdown = render_markdown(snapshot, lang=args.lang, max_items=args.max_items)
    output = _save(args.output, markdown, args.force)
    data = {"snapshot": snapshot, "summary": summarize(snapshot), "markdown": markdown, "output": output}
    return data, f"Saved report: {output}" if output else markdown.rstrip(), 0 if snapshot["coverage"]["complete"] else 3


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in arguments
    if as_json:
        arguments = [argument for argument in arguments if argument != "--json"]
    try:
        args = _parser().parse_args(arguments)
        data, human, status = _execute(args)
        if as_json:
            print(json.dumps({"ok": True, "data": data}, ensure_ascii=False))
        else:
            print(human)
        if status == 3:
            print("Partial data: a page limit was reached. Increase --max-pages and collect again.", file=sys.stderr)
        return status
    except (CLIError, GitHubError, ValueError, OSError) as exc:
        if isinstance(exc, CLIError):
            code, status = exc.code, exc.status
        elif isinstance(exc, GitHubError):
            code, status = "github_error", 1
        elif isinstance(exc, OSError):
            code, status = "file_error", 1
        else:
            code, status = "invalid_input", 2
        message = str(exc)
        # Local paths or input errors can also contain a token; never echo one.
        token, _ = _token()
        if token:
            message = message.replace(token, "[REDACTED]")
        if as_json:
            print(json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False))
        else:
            print(f"Error: {message}", file=sys.stderr)
        return status
    except KeyboardInterrupt:
        if as_json:
            print(json.dumps({"ok": False, "error": {"code": "interrupted", "message": "Interrupted."}}))
        else:
            print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
