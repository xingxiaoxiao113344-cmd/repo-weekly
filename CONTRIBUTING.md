# Contributing

Repo Weekly welcomes reproducible bug reports, documentation fixes, and small changes that make maintenance reports more useful. The project is at an early stage; discuss larger features in an issue before investing in implementation.

## Run locally

Use Python 3.11 or newer from the repository root:

```sh
python -m pip install .
python -m unittest discover -s tests -v
repo-weekly doctor --offline
repo-weekly demo --lang en
repo-weekly demo --lang zh
```

Tests must work without credentials or live network requests. Use local fixtures or mocked HTTP responses. A live repository check can help manual verification, but should not become a required automated test.

## Scope and behavior

- Keep the default reporting path deterministic and free of third-party runtime dependencies.
- Keep all GitHub requests read-only and restricted to the GitHub API host.
- Preserve the JSON success/error envelope when changing command output.
- Preserve the UTC interval convention: start inclusive, end exclusive.
- Surface incomplete coverage. Do not silently turn a page limit or failed source into a complete-looking report.
- Keep English and Chinese documentation and report labels consistent. Do not claim that source titles are translated.
- Do not commit credentials or nonpublic repository data. Use fictional data for new fixtures and label it as such.

Bug fixes should include a focused regression test when the behavior warrants one. Documentation-only changes do not need artificial tests.

## Pull requests

Describe the concrete problem, resulting behavior, and validation performed. Include sample output when it helps explain a user-visible change. Keep unrelated cleanup separate so the change is easier to review.

By contributing, you agree that your contributions are licensed under this repository's MIT License.
