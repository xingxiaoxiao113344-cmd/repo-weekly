# Repo Weekly

[简体中文](README.zh-CN.md)

Turn a GitHub repository's recent issues, pull requests, and releases into a Markdown maintenance report. Save the collected data as JSON and render the report again without a network connection.

Repo Weekly is an early-stage, read-only command-line tool. Reports use deterministic templates; no AI model or OpenAI API is called. It does not post comments, change issues, merge pull requests, or write to a GitHub repository.

## Requirements and installation

Python 3.11 or newer. There are no third-party runtime dependencies.

From this project's directory:

```sh
python -m pip install .
repo-weekly doctor --offline
repo-weekly demo --lang en
```

The demo uses explicitly fictional fixture data. Its repository, people, activity, and counts are examples, not evidence of real users or project adoption.

On Windows, you can also run directly from the source folder without installing:

```powershell
.\run.ps1 demo --lang en --output demo.md
.\run.ps1 report pallets/click --days 7 --output weekly.md
```

See the [English demo report](examples/demo-report.en.md) and
[Chinese demo report](examples/demo-report.zh.md).

## Create a report

```sh
repo-weekly repo python/cpython
repo-weekly report python/cpython --days 7 --lang en --output weekly.md
```

Repository inputs accept `OWNER/REPO` or a GitHub repository URL. `--lang en` and `--lang zh` select report headings and labels. Original issue, pull request, and release titles are not translated. `--max-items` limits the displayed entries in each section; summary counts still use all collected records.

The tool uses GitHub's public REST API. Public repository requests can run without a token, subject to GitHub's access and rate limits. If you supply a token, set `GITHUB_TOKEN` or `GH_TOKEN` in the environment; `GITHUB_TOKEN` takes precedence. Repo Weekly never intentionally prints either token. Use only the access needed to read the target repository.

## Save data and work offline

Choose an explicit end time when you want to record an exact reporting window:

```sh
repo-weekly collect python/cpython --days 7 --until 2026-10-22T00:00:00Z --output snapshot.json
repo-weekly report python/cpython --data snapshot.json --lang en --output weekly.md
```

`collect` contacts GitHub and saves a snapshot. `report --data` reads the snapshot locally and uses its saved window; do not combine `--data` with `--days` or `--until`. Keep the saved JSON if you need to inspect or reproduce a report. Repository content in a snapshot may be sensitive when collected using access to a private repository; review files before sharing them.

Output files are created without replacing an existing file. Add `--force` when you intend to overwrite one:

```sh
repo-weekly report python/cpython --data snapshot.json --output weekly.md --force
```

## Reporting window and coverage

Windows use UTC and include the start while excluding the end: `[since, until)`. `--days 7` selects seven days ending at `--until`, or at the current time when `--until` is omitted. `--until` accepts a UTC date or an ISO timestamp that includes a timezone.

Reports summarize issues opened and closed, pull requests opened and merged, pull requests closed without merging, releases, and active issues and pull requests. Counts describe the collected data and the tool's documented window, rather than a complete audit history.

Two limitations matter when reading a report:

- GitHub's current issue and pull request records cannot reconstruct every historical reopening, earlier closure, or earlier state. A collection performed later may not recreate the exact history of an old period.
- Collection has a page limit for each source. The default is 10 pages; `--max-pages` changes it. When collection reaches the limit with more results available, the snapshot and report identify the affected coverage as partial. Treat those counts as incomplete.

Review the coverage warnings in the report before using its counts. Increasing `--max-pages` can collect more data, but it does not recover unavailable state history.

Partial collection or reporting returns exit status **3**, with the available data, a warning on standard error, and `ok: true` in JSON mode. Complete results return 0; invalid input returns 2; API and file errors return 1.

## Commands

| Command | Purpose |
| --- | --- |
| `repo-weekly doctor --offline` | Inspect local authentication availability and bundled fixture availability without network requests. |
| `repo-weekly doctor --check-network` | Include a GitHub connectivity check. |
| `repo-weekly repo OWNER/REPO` | Read repository metadata. |
| `repo-weekly repos OWNER --limit 20` | List repositories for an owner. |
| `repo-weekly collect OWNER/REPO --days 7 --output snapshot.json` | Collect a snapshot for a report. |
| `repo-weekly report OWNER/REPO --days 7 --lang zh --max-items 20` | Render a maintenance report. |
| `repo-weekly demo --lang zh --output demo.md` | Render a fictional example without network access. |
| `repo-weekly api /repos/OWNER/REPO` | Make a read-only GET request to `api.github.com`. |

Use `repo-weekly --help` or `repo-weekly COMMAND --help` for options. The `api` command is limited to GitHub's API host; it is not a general HTTP client.

## JSON for scripts

Add `--json` before or after the subcommand:

```sh
repo-weekly --json doctor --offline
repo-weekly repo python/cpython --json
repo-weekly --json report python/cpython --data snapshot.json --lang en
```

Successful responses use `{"ok": true, "data": ...}`. Errors use `{"ok": false, "error": {"code": ..., "message": ...}}`. The report response includes its snapshot, summary, Markdown, and output information. See [the JSON interface](docs/JSON.md).

If your shell cannot find `repo-weekly` after installation, run the equivalent command as `python -m repo_weekly`, for example `python -m repo_weekly demo --lang en`.

## Development

```sh
python -m pip install .
python -m unittest discover -s tests -v
```

The automated test suite uses local fixtures and mocked network responses. CI runs it on Ubuntu and Windows with Python 3.11, 3.12, and 3.13; the tests do not need a GitHub token or live API calls. Package installation in CI may download build tooling.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). This project is licensed under the [MIT License](LICENSE).

## Next steps

Potential future work includes optional AI-assisted summaries, more historical event coverage, and feedback from maintainers using the reports. Those features are not implemented in this version. The current reporting path works without an OpenAI account or API credits.

For an honest starting checklist and a draft Codex for Open Source application, see [申请准备说明](docs/APPLICATION.zh-CN.md). Opening a repository does not guarantee acceptance into any funding or access program.
