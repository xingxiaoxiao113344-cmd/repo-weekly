---
name: repo-weekly
description: Generate or inspect source-linked GitHub maintenance reports using the installed repo-weekly CLI, including offline snapshots and English or Chinese headings.
---

Use `repo-weekly --help` to verify that the command is installed, then run
`repo-weekly --json doctor --offline`. Network access is unnecessary for saved
snapshots and the fictional demo. Public GitHub reads work without auth;
`GITHUB_TOKEN` takes precedence over `GH_TOKEN` when present.

When the repository is unknown, `repo-weekly --json repos OWNER --limit 20`
discovers public repositories. `repo-weekly --json repo OWNER/REPO` resolves a
name or canonical GitHub URL to metadata.

For a fresh report, collect a JSON snapshot first when reproducibility matters,
then render it. Saved snapshots carry their own UTC time window, so omit
`--days` and `--until` when using `--data`.

```bash
repo-weekly collect OWNER/REPO --days 7 --output snapshot.json
repo-weekly report OWNER/REPO --data snapshot.json --lang zh --output weekly.md
repo-weekly --json api /repos/OWNER/REPO
```

`--json` returns `{ok:true,data:...}` or `{ok:false,error:{code,message}}`.
Exit code 3 means a report was generated with partial collection coverage;
inspect `snapshot.coverage` and increase `--max-pages` before drawing conclusions
from counts. A complete collection still represents current GitHub records,
not a complete history of reopenings, prior states, or deleted objects.

The raw `api` command supports GET requests to `api.github.com` only. The tool
does not publish reports or comments. Publishing, repository creation, and
application submission require a separate user request. Preserve existing
output files unless replacing them is intended; `--force` permits replacement.

`--lang` localizes headings and labels, preserving original titles. Do not
describe generated reports as AI summaries. Demo records are explicitly
fictional and cannot establish project adoption.
