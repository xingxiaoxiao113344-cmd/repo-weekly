# Security

Repo Weekly is an early-stage tool. Security fixes are handled on the current main branch; there is no separate long-term support release line.

## Reporting a vulnerability

If this repository's GitHub Security tab offers **Report a vulnerability**, use it for a private report. Include the affected command or code path, a minimal reproduction, and the expected impact. Remove credentials and private repository content.

If private reporting has not been enabled, open a public issue requesting a private contact channel without including exploit details, tokens, or sensitive data. The maintainer should enable GitHub private vulnerability reporting before inviting external use.

No response-time commitment is offered at this stage.

## Data and credentials

- Authentication is read from `GITHUB_TOKEN`, falling back to `GH_TOKEN`. Do not put tokens in command arguments, issue reports, or committed files.
- Commands perform GET requests to GitHub's API and do not write to GitHub repositories.
- Reports and JSON snapshots can contain repository content. Treat exports from private repositories according to that content's access requirements.
- `--output` refuses to replace an existing file unless `--force` is supplied. Check the chosen output path before using `--force`.
- Repository titles and descriptions are external text. Review generated Markdown before publishing it elsewhere.

This tool creates activity reports. It does not perform vulnerability scans or certify a repository's security.
