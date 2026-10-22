# GitHub data sources

Repo Weekly uses the GitHub REST API at `https://api.github.com`, with
`Accept: application/vnd.github+json` and API version `2022-11-28`.

| Source | Endpoint | Collection behavior |
| --- | --- | --- |
| Repository metadata | `GET /repos/{owner}/{repo}` | Resolve the canonical repository name. |
| Issues | `GET /repos/{owner}/{repo}/issues` | All states, sorted by update time. Request `since` one second before the window start, then filter locally to the exact window. Exclude entries containing `pull_request`. |
| Pull requests | `GET /repos/{owner}/{repo}/pulls` | All states, sorted by update time descending. Stop after reaching records older than the window. Use the list response's `merged_at`. |
| Releases | `GET /repos/{owner}/{repo}/releases` | Traverse pages and filter on `published_at`. Skip drafts. Do not assume publication order matches creation order. |
| Discovery | `GET /users/{owner}/repos` | Bounded list of public repositories. |
| Connectivity | `GET /rate_limit` | Only requested by `doctor --check-network`. |

Pagination follows the `Link` header's `rel="next"`. A page cap is only marked
as incomplete when more pages actually remain. API errors stop collection;
they are never turned into empty, complete-looking results. A complete
collection means all pages needed by these queries were read, not that every
historical event can be reconstructed.

Requests use GET only and refuse redirects and other hosts. Tokens are read
from environment variables; HTTP error messages omit request URLs and bodies.
Renamed repositories should be supplied under their current canonical name.

Official references:

- [Issues, including pull requests](https://docs.github.com/en/rest/issues/issues#list-repository-issues)
- [Pull request list fields and ordering](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests)
- [Releases](https://docs.github.com/en/rest/releases/releases#list-releases)
- [Pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)
- [API versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions)
- [REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
