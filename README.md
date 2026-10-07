# GitHub Issue Snapshot Connector

A small Python connector that imports open issues from a public GitHub repository into a local SQLite database, then reads them back without calling GitHub again.

For design details (components, data flow, schema, tradeoffs) see [Architecture.MD](Architecture.MD).

## Features

- **Import:** fetch one page of open issues for `owner/name` from the GitHub API, exclude pull requests, and save them to SQLite.
- **Idempotent:** importing the same repository again updates existing rows instead of creating duplicates.
- **Read:** return saved issues for a repository from SQLite only (no network call). Data persists across restarts.
- **Reusable interface:** `import_issues()` and `read_issues()` return JSON-compatible dictionaries.
- **Configurable:** the database path can be set by the caller.
- **Useful errors:** clear error results for invalid repository names, missing repositories, rate limits, and network or API failures.

## Prerequisites

- Python 3.9 or newer (check with `python3 --version`)
- `pip`
- Internet access for real imports (no GitHub token is needed for public repositories)

## Dependencies

| Package | Purpose |
| --- | --- |
| `requests` | HTTP calls to the GitHub API |
| `urllib3<2` | Pinned to avoid a LibreSSL warning on macOS system Python |
| `pytest` | Running the automated tests |
| `sqlite3` | Built into Python, no install needed |

## Local Setup

```bash
git clone https://github.com/neilsyal123-web/rocketride.git
cd rocketride

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Running the Connector

All commands are run from the repository root. The database path defaults to `issues.db` in the current directory and can be changed with `--db`.

Import open issues:

```bash
python3 app/connector.py import psf/requests --db issues.db
```

Read saved issues (no network call):

```bash
python3 app/connector.py read psf/requests --db issues.db
```

Show help:

```bash
python3 app/connector.py --help
```

Using it as a library (from inside the `app/` folder):

```python
from connector import import_issues, read_issues

result = import_issues("psf/requests", db_path="issues.db")
saved = read_issues("psf/requests", db_path="issues.db")
```

## Running the Tests

```bash
python3 -m pytest app/tests -v
```

The tests use mocked GitHub responses (no network needed) and cover:

- import and read
- repeated imports without duplicates (including updating a changed title)
- API failures: HTTP 500, repository not found (404), and a network failure
- a failed import not damaging previously saved data
- an invalid repository name never calling GitHub

## Example Inputs and Outputs

### Import

Input:

```bash
python3 app/connector.py import psf/requests --db issues.db
```

Output:

```json
{
  "ok": true,
  "repository": "psf/requests",
  "imported": 15
}
```

`imported` is 15 rather than 30 because GitHub returned one page of 30 items and about half were pull requests, which are excluded.

### Read

Input:

```bash
python3 app/connector.py read psf/requests --db issues.db
```

Output (shortened):

```json
{
  "ok": true,
  "repository": "psf/requests",
  "count": 15,
  "issues": [
    {
      "number": 7632,
      "title": "Lingering docstring references to python2.7 cookielib",
      "url": "https://github.com/psf/requests/issues/7632"
    },
    {
      "number": 7631,
      "title": "TestTimeout abandons three delay/10 requests and later tests wait out the server",
      "url": "https://github.com/psf/requests/issues/7631"
    }
  ]
}
```

### Repeated import (no duplicates)

Running the same import a second time returns the same result, and the number of saved rows stays at 15:

```json
{
  "ok": true,
  "repository": "psf/requests",
  "imported": 15
}
```

### Error case: invalid repository

Input:

```bash
python3 app/connector.py import nonsense --db issues.db
```

Output (exit code 1):

```json
{
  "ok": false,
  "error": "Invalid repository 'nonsense'. Expected format: owner/name"
}
```

## Configuration

| Setting | How to set it | Default |
| --- | --- | --- |
| Database path | `--db` flag on the command line, or the `db_path` argument in code | `issues.db` |

## Project Structure

```
.
├── README.md
├── Architecture.MD
├── requirements.txt
└── app/
    ├── connector.py
    └── tests/
        └── test_connector.py
```

## Tools Used

### AI tools

| Tool | What it helped me do |
| --- | --- |
| Claude | Explained the `requests` library and the GitHub Issues API, planned the build in small steps, suggested the SQLite schema and upsert approach, helped draft the mocked tests, and helped debug environment and git problems |

### Other tools

| Tool | What it was used for |
| --- | --- |
| GitHub REST API (Issues endpoint) | The data source; I inspected real responses to learn the fields |
| SQLite and the `sqlite3` command line | Storage, and inspecting the database to verify row counts and contents |
| `requests` | Making HTTP calls |
| `pytest` | Running the automated tests |
| VS Code | Writing and running the code |
| Git and GitHub | Version control and hosting the repository |
| Screen recorder | Recording the demo video |

## An Unfamiliar Problem I Solved With AI

**The problem:** I did not know that GitHub's "list issues" endpoint also returns pull requests, because GitHub treats every pull request as an issue. The challenge says to exclude pull requests, so I needed a reliable way to tell them apart.

**What I asked AI:** How to fetch only real issues from `GET /repos/{owner}/{name}/issues`, and how to recognize pull requests in the response.

**What the AI suggested:** Pull requests include a `pull_request` key in their JSON object, so filter out any item that has that key. It also pointed out that this filtering happens after fetching, so a page of 30 items can yield fewer than 30 issues.

**How I verified it:**

- I called the API directly and inspected the raw response to confirm that some items had a `pull_request` key and others did not.
- After importing, I checked the database, and no saved URL contained `/pull/`.
- I confirmed the count: a real import returned 15 issues from a page of 30 items, which matches the behavior of removing pull requests.
- I wrote a mocked test with one pull request in the fake response and asserted that it is not saved.

**What I corrected or learned:** The AI's advice was right, but I had to verify the side effect myself: "one page" is not "30 issues." I documented that tradeoff in Architecture.MD. I also hit a separate environment issue: plain `pytest` ran my conda Python instead of my virtual environment, so I switched to `python3 -m pytest`, which uses the active venv.

## Limitations

- Fetches a single page of open issues only (no pagination), by design.
- Because only open issues are fetched, an issue that is later closed on GitHub stays in the local database until it is removed manually.
- Public repositories only, no authentication. Unauthenticated GitHub requests are limited to about 60 per hour.
- No UI or hosted deployment.