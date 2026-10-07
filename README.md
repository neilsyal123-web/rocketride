# GitHub Issue Snapshot Connector

A small Python connector that imports open issues from a public GitHub repository into a local SQLite database and reads them back without calling GitHub again.

For design details (components, data flow, schema, tradeoffs) see [Architecture.MD](Architecture.MD).

## Features

- **Import:** fetch one page of open issues for `owner/name` from the GitHub API, excluding pull requests, and save them to SQLite.
- **Idempotent:** importing the same repository again updates existing rows instead of creating duplicates.
- **Read:** return saved issues for a repository from SQLite only (no network). Data persists across restarts.
- **Reusable interface:** `import_issues()` and `read_issues()` return JSON-compatible results.
- **Configurable:** the database path can be set by the caller.
- **Errors:** clear error results for invalid repository names and failed API requests.

## Prerequisites

- Python 3.9 or newer (check with `python3 --version`)
- `pip`
- Internet access for real imports (no GitHub token needed for public repos)

## Dependencies

| Package | Purpose |
| --- | --- |
| `requests` | HTTP calls to the GitHub API |
| `pytest` | Running the automated tests |
| `sqlite3` | Built into Python, no install needed |

Install everything with:

```bash
pip install -r requirements.txt
```

## Local Setup

```bash
git clone https://github.com/neilsyal123-web/rocketride.git
cd rocketride

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Running the Connector

Import issues:

```bash
python3 app/connector.py import owner/name --db issues.db
```

Read saved issues:

```bash
python3 app/connector.py read owner/name --db issues.db
```

Using it as a library:

```python
from app.connector import import_issues, read_issues

result = import_issues("owner/name", db_path="issues.db")
issues = read_issues("owner/name", db_path="issues.db")
```

## Example Inputs and Outputs

**Import**

Input:

```bash
python3 app/connector.py import psf/requests
```

Output:
Illustrative output; actual issues and counts will vary.
```json
{ "ok": true, "repository": "psf/requests", "imported": 1 }
```

**Read**

Input:

```bash
python3 app/connector.py read psf/requests
```

Output:
Illustrative output; actual issues and counts will vary.
```json
{
  "ok": true,
  "repository": "psf/requests",
  "count": 1,
  "issues": [
    {
      "number": 123,
      "title": "Example issue title",
      "url": "https://github.com/psf/requests/issues/123"
    }
  ]
}
```

**Error case (invalid repository)**

Input:

```bash
python3 app/connector.py import not-a-valid-repo
```

Output:

```json
{
  "ok": false,
  "error": "Invalid repository 'not-a-valid-repo'. Expected format: owner/name"
}
```

## Configuration

| Setting | How to set it | Default |
| --- | --- | --- |
| Database path | `--db` flag / `db_path` argument | `issues.db` |

## Running the Tests

```bash
python3 -m pytest app/tests -v
```

The tests use mocked GitHub responses and cover:

- import and read
- repeated imports without duplicates
- an API failure

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
| Claude (using Claude Projects) | I kept this project in a Claude Project so the challenge brief, my notes, and the conversation history stayed in one place. I used it to learn the `requests` library and the GitHub Issues API, break the build into small steps, design the SQLite schema and the upsert that prevents duplicates, plan error handling, write the mocked tests, debug environment problems (virtual environment, running `pytest` with the wrong Python, files tracked by git), and draft the README and Architecture documents. I ran and checked every step myself before moving on. |

### Other tools

| Tool | What it was used for |
| --- | --- |
| GitHub REST API (Issues endpoint) | The data source. I called it directly and inspected real responses to learn the fields, including how pull requests are marked with a `pull_request` key |
| `sqlite3` command-line tool | Inspecting the database to confirm row counts, check that repeated imports create no duplicates, and check that no pull request URLs were saved |
| `requests` (Python library) | Making the HTTP calls to the GitHub API |
| `pytest` | Running the automated tests with mocked API responses |
| VS Code | Writing the code and running it in the integrated terminal |
| Git and GitHub | Version control and hosting the repository |
| QuickTime Player | Recording the demo video |

## An Unfamiliar Problem I Solved With AI

**The problem:** The challenge says to exclude pull requests, but I did not know how to tell pull requests apart from issues. GitHub's "list issues" endpoint returns both, because GitHub treats every pull request as an issue.

**What I asked AI:** I asked Claude to walk me through the project step by step. Its first step was to inspect what the Issues endpoint actually returns and to check whether any items have a `pull_request` key, before designing anything.

**What the AI suggested:** Pull requests carry a `pull_request` key in their JSON, so the fix is to drop any item that has it. It also warned that this filtering happens after fetching, so one page of 30 items can yield fewer than 30 issues.

**How I verified it:**

- A real import of `psf/requests` saved 15 issues from a page of 30 items, which matches pull requests being removed.
- The saved URLs I inspected all contain `/issues/`, and none contain `/pull/`.
- I wrote a mocked test where the fake API response includes one pull request, and the test asserts that only the 2 real issues are saved.
- Importing the same repository twice kept the count at 15, so the filter did not interfere with the duplicate prevention.

**What I corrected or learned:** The filtering advice was correct, but it taught me that "one page" does not mean "30 issues," and I documented that tradeoff in Architecture.MD. I also had to correct an AI-suggested command: it told me to run plain `pytest`, which picked up my conda Python instead of my virtual environment and found no tests. I diagnosed this from the Python path shown in the pytest header and switched to `python3 -m pytest`, which uses the active venv.

## Limitations

- Fetches a single page of open issues only (no pagination).
- Public repositories only; no authentication.
- No UI or hosted deployment.