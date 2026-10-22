# JSON interface

Use `--json` to request a single machine-readable response on standard output. It can appear before or after the subcommand:

```sh
repo-weekly --json doctor --offline
repo-weekly repo python/cpython --json
```

## Response envelope

Every successful command wraps its result in `data`:

```json
{"ok": true, "data": {}}
```

The empty object above illustrates the envelope, not the complete payload of a particular command. A failed command uses:

```json
{"ok": false, "error": {"code": "...", "message": "..."}}
```

`error.code` is a machine-readable identifier; `error.message` explains the failure. Check both `ok` and the process status before using `data`; do not parse human-readable terminal output.

| Exit status | Meaning |
| --- | --- |
| `0` | Command completed with complete collection coverage, where applicable. |
| `1` | GitHub API or file operation failed. |
| `2` | Arguments, timestamps, or snapshot input are invalid. |
| `3` | Command produced a partial snapshot or report after reaching a page limit. `ok` remains `true`; inspect `data.snapshot.coverage`. A warning is also written to standard error. |
| `130` | Interrupted by the user. |

Consumers should tolerate additional fields and should not depend on JSON object key order.

## Command payloads

| Command | `data` |
| --- | --- |
| `doctor` | Local diagnostics including `auth_available`, `auth_source`, `auth_required`, `offline`, `fixture_available`, and `network_checked`. A network check is requested with `--check-network`. |
| `repo` | Repository metadata returned by GitHub. |
| `repos` | The requested owner's repository listing, constrained by `--limit`. |
| `api` | The response to the selected GitHub REST GET request. |
| `collect` | An object containing `snapshot` and `output`. `output` is `null` unless an output file was written. |
| `report` | An object containing `snapshot`, `summary`, `markdown`, and `output`. |
| `demo` | The same fields as `report`, rendered from the bundled fictional fixture. It must not be interpreted as real repository activity. |

The authentication diagnostic reports availability and source, never the token value. `auth_source` is `GITHUB_TOKEN`, `GH_TOKEN`, or `missing`. `auth_required` is `false`. `offline` records whether `--offline` was supplied; `network_checked` records whether `--check-network` was supplied. A plain `doctor` command also avoids the network.

## Snapshot and summary meaning

A snapshot has these fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Currently `1`. |
| `repository` | Metadata including `full_name`, `html_url`, and `description`. |
| `window` | The `since` and `until` UTC timestamps. |
| `generated_at` | When the snapshot was collected or created. |
| `issues` | Collected issue objects, excluding pull requests. |
| `pull_requests` | Collected pull request objects. |
| `releases` | Collected published release objects. |
| `coverage.complete` | Whether collection avoided page-limit truncation; it does not assert full historical reconstruction. |
| `coverage.warnings` | A list of collection coverage warnings. |
| `fixture` | Set to `true` in the bundled fictional demo. |

`summary` contains integer counts with these keys: `issues_opened`, `issues_closed`, `prs_opened`, `prs_merged`, `prs_closed_unmerged`, `releases`, `active_issues`, and `active_prs`. An issue or PR is active when at least one of its available `created_at`, `updated_at`, `closed_at`, or `merged_at` timestamps falls in the reporting window. Each active record is counted once. A release is counted by `published_at`.

The reporting window is UTC and follows `[since, until)`: the start is included and the end is excluded. Counts come from the snapshot's records. The snapshot is a collection of GitHub's currently available records, not a full historical event ledger; previous closures and reopenings may not be recoverable.

Always inspect coverage information. Each source defaults to a maximum of 10 pages, configurable using `--max-pages`. If another page remains when the limit is reached, the data is partial. An incomplete collection must not be treated as a complete count, even when the command itself succeeds.

## Files versus command responses

`collect --output snapshot.json` writes the snapshot itself to disk, while its JSON command response wraps the snapshot and output information in the success envelope. Without `--json` or `--output`, `collect` prints the raw snapshot. Feed a saved snapshot file to `report --data`:

```sh
repo-weekly --json collect python/cpython --days 7 --until 2026-10-22T00:00:00Z --output snapshot.json
repo-weekly --json report python/cpython --data snapshot.json --lang en --output weekly.md
```

`report --output weekly.md` writes Markdown to disk. Its JSON response still includes `markdown`. The `--json` option changes terminal output, not the report file's format.

Existing output files are refused unless `--force` is specified. Offline replay with `--data` does not call GitHub and uses the saved window, so `--days` and `--until` are rejected with `--data`. The requested repository must match `snapshot.repository.full_name`. Saving the snapshot lets a consumer retain the data behind a report even if the live repository changes later.

## Interface maturity

This is an early-stage interface. Preserve snapshots together with the project version that generated them. Review the changelog before updating automated integrations; the envelope is designed for scripting, but the project has not declared a long-term schema compatibility guarantee.
