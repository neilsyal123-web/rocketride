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

- Python [3.x] (check with `python3 --version`)
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
git clone [your-repo-url]
cd [repo-folder]

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
python3 app/connector.py import [owner/name]
```

Output:

```json
{ "ok": true, "repository": "owner/name", "imported": 0 }
```

**Read**

Input:

```bash
python3 app/connector.py read [owner/name]
```

Output:

```json
{
  "ok": true,
  "repository": "owner/name",
  "issues": [
    { "number": 1, "title": "...", "url": "https://github.com/owner/name/issues/1" }
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
{ "ok": false, "error": "..." }
```

## Configuration

| Setting | How to set it | Default |
| --- | --- | --- |
| Database path | `--db` flag / `db_path` argument | [default path] |

## Running the Tests

```bash
pytest app/tests -v
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
| [e.g. Claude] | [e.g. researching the GitHub Issues API, planning the schema, debugging] |
| [other AI tool] | [...] |

### Other tools

| Tool | What it was used for |
| --- | --- |
| [e.g. GitHub REST API docs] | [...] |
| [e.g. DB Browser for SQLite] | [e.g. inspecting the database to confirm no duplicates] |
| [e.g. pytest] | [...] |
| [e.g. screen recorder] | [demo video] |

## An Unfamiliar Problem I Solved With AI

**The problem:** [What you didn't know or couldn't figure out, e.g. how pull requests show up in the issues endpoint.]

**What I asked AI:** [Summarize the question or prompt.]

**What the AI suggested:** [Summarize its answer.]

**How I verified it:** [e.g. called the API by hand, inspected the real response, checked the docs, ran a test.]

**What I corrected or learned:** [Anything the AI got wrong or incomplete, and what you changed.]

## Limitations

- Fetches a single page of open issues only (no pagination).
- Public repositories only; no authentication.
- No UI or hosted deployment.