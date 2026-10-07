# Architecture

A small connector that copies open issues from a public GitHub repository into a local SQLite database and serves them back from that database.

## Interface

The connector exposes two reusable functions in app/connector.py. Both return JSON-compatible dictionaries for successful operations and expected failures.

```python
import_issues(repo: str, db_path: str = "issues.db") -> dict
read_issues(repo: str, db_path: str = "issues.db") -> dict
```

**Success results**

```json
{ "ok": true, "repository": "psf/requests", "imported": 15 }
```

```json
{
  "ok": true,
  "repository": "psf/requests",
  "count": 1,
  "issues": [{ "number": 7632, "title": "...", "url": "https://github.com/psf/requests/issues/7632" }]
}
```

**Failure result (same shape for both functions)**

```json
{ "ok": false, "error": "Invalid repository 'nonsense'. Expected format: owner/name" }
```

A thin command-line wrapper (`main()` using `argparse`) calls these same functions, prints the result as JSON, and exits with code 0 on success or 1 on failure.

## Main Components

| Component | Responsibility |
| --- | --- |
| `parse_repo` | Validates that the input is `owner/name` and splits it. Raises `ConnectorError` on bad input. |
| `fetch_open_issues` | The only function that talks to GitHub. Fetches one page of open issues, filters out pull requests, and converts failures into `ConnectorError`. |
| `get_connection` | Opens the SQLite file and creates the `issues` table if it does not exist. |
| `import_issues` | Public entry point: validate, fetch, then save with an upsert. |
| `read_issues` | Public entry point: validate, then read from SQLite only. |
| `ConnectorError` | One internal exception type for all expected failures. |
| `main` | Command-line wrapper around the two public functions. |

## Data Flow

**Import**

```
"owner/name"
   -> parse_repo            (validate, split)
   -> fetch_open_issues     (GET /repos/{owner}/{name}/issues, state=open, one page)
   -> drop items that have a "pull_request" key
   -> map to (repository, number, title, html_url)
   -> INSERT ... ON CONFLICT DO UPDATE   (inside one transaction)
   -> {"ok": true, "imported": N}
```

**Read**

```
"owner/name"
   -> parse_repo
   -> SELECT from SQLite WHERE repository = ?   (no network call)
   -> {"ok": true, "count": N, "issues": [...]}
```

## Database Schema

One table, stored in a SQLite file so data persists across restarts:

```sql
CREATE TABLE IF NOT EXISTS issues (
    repository TEXT    NOT NULL,
    number     INTEGER NOT NULL,
    title      TEXT    NOT NULL,
    url        TEXT    NOT NULL,
    PRIMARY KEY (repository, number)
);
```

- The composite primary key `(repository, number)` identifies one issue. An issue number alone is not unique across repositories.
- Because the database enforces this key, repeated imports use `ON CONFLICT(repository, number) DO UPDATE` to refresh the title and URL instead of adding duplicate rows.
- `url` stores GitHub's `html_url` (the page a person would open), not the API URL.
- `repository` is stored lowercase, because GitHub treats `Psf/Requests` and `psf/requests` as the same repository.

## Configuration

| Setting | Where | Default |
| --- | --- | --- |
| Database path | `db_path` argument, or `--db` on the command line | `issues.db` |
| GitHub API base URL | `GITHUB_API` constant | `https://api.github.com` |
| Request timeout | Fixed at 10 seconds in `fetch_open_issues` | 10 s |
| Page size | `per_page=30`, one page only | 30 |

No token or environment variable is required for public repositories.

## Error Handling

Internal helpers raise ConnectorError for expected input, network, API, and database failures. The public functions catch these errors and return {"ok": false, "error": ...}. Unexpected exceptions may still propagate.

Imports run inside a single transaction, so a failure never leaves a half-saved import. A failed API call also happens before any database write, so previously saved data is untouched.

## Key Design Tradeoffs

- **Errors as return values, not exceptions.** Callers get a predictable `ok` flag and can serialize every result as JSON. The cost is that callers must check `ok` instead of using `try/except`.
- **Filtering pull requests after fetching.** The endpoint returns issues and pull requests together. Filtering a page of up to 30 items can leave fewer than 30 issues. Additional pages are outside this challenge’s scope.
- **Open issues only, no deletion.** An issue that is closed on GitHub after being imported stays in the local database as a stale row. Detecting this would require comparing against the full open set or tracking state.
- **Upsert instead of delete-and-reinsert.** Updating in place by primary key is simpler, atomic, and never leaves a window where data is missing.
- **Lowercasing the repository name.** This prevents duplicates from different capitalizations, at the cost of not preserving the exact capitalization the user typed.
- **Fetching is separated from storage.** `fetch_open_issues` is the only place that touches the network, so tests can mock it without involving the database.
- **New connection per call.** Each function opens and closes its own SQLite connection. This is simple and safe for a script, but not optimized for high call volume.
- **No authentication.** Public repositories need no token, but unauthenticated requests are limited to about 60 per hour.
- **`read_issues` on a missing database.** Opening a database path that does not exist creates an empty database and returns zero issues, instead of failing.

## Testing

Tests are in `app/tests/test_connector.py` and run with `python3 -m pytest app/tests -v`. They replace `requests.get` with a fake response, so they run offline and deterministically. A temporary database is created for each test. Coverage: import and read, repeated imports without duplicates (including an updated title), HTTP 500, HTTP 404, a network failure, a failed import preserving existing data, and an invalid repository never reaching GitHub.