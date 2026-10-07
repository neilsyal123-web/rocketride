import re
import sqlite3
import requests
import argparse
import json
import sys

GITHUB_API = "https://api.github.com"
DEFAULT_DB_PATH = "issues.db"


class ConnectorError(Exception):
    """Raised for invalid input or failed API requests."""

def parse_repo(repo):
    """Turn 'owner/name' into ('owner', 'name'), or raise ConnectorError."""
    if not isinstance(repo, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ConnectorError(f"Invalid repository '{repo}'. Expected format: owner/name")
    owner, name = repo.split("/")
    return owner, name


def fetch_open_issues(owner, name):
    """Fetch one page of open issues (pull requests excluded) from GitHub."""
    url = f"{GITHUB_API}/repos/{owner}/{name}/issues"
    params = {"state": "open", "per_page": 30}
    headers = {"Accept": "application/vnd.github+json"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        raise ConnectorError(f"Could not reach GitHub: {e}") from e

    if response.status_code == 404:
        raise ConnectorError(f"Repository '{owner}/{name}' was not found.")
    if response.status_code in (403, 429):
        raise ConnectorError("GitHub rate limit reached or access denied. Try again later.")
    if response.status_code != 200:
        raise ConnectorError(f"GitHub API error: HTTP {response.status_code}")

    try:
        items = response.json()
    except ValueError as e:
        raise ConnectorError("GitHub returned a response that was not valid JSON.") from e

    return [item for item in items if "pull_request" not in item]


def get_connection(db_path=DEFAULT_DB_PATH):
    """Open the SQLite database and make sure the issues table exists."""
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as e:
        raise ConnectorError(f"Could not open database '{db_path}': {e}") from e

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS issues (
                repository TEXT    NOT NULL,
                number     INTEGER NOT NULL,
                title      TEXT    NOT NULL,
                url        TEXT    NOT NULL,
                PRIMARY KEY (repository, number)
            )
            """
        )
        conn.commit()
    except sqlite3.Error as e:
        conn.close()
        raise ConnectorError(f"Could not set up database '{db_path}': {e}") from e

    return conn

def import_issues(repo, db_path=DEFAULT_DB_PATH):
    """Import open issues for 'owner/name' into SQLite. Returns a JSON-compatible dict."""
    try:
        owner, name = parse_repo(repo)
        repository = f"{owner}/{name}".lower()
        issues = fetch_open_issues(owner, name)
        rows = [(repository, i["number"], i["title"], i["html_url"]) for i in issues]

        conn = get_connection(db_path)
        try:
            with conn:
                conn.executemany(
                    """
                    INSERT INTO issues (repository, number, title, url)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(repository, number)
                    DO UPDATE SET title = excluded.title, url = excluded.url
                    """,
                    rows,
                )
        except sqlite3.Error as e:
            raise ConnectorError(f"Could not save issues: {e}") from e
        finally:
            conn.close()
    except ConnectorError as e:
        return {"ok": False, "error": str(e)}

    return {"ok": True, "repository": repository, "imported": len(rows)}

def read_issues(repo, db_path=DEFAULT_DB_PATH):
    """Return saved issues for 'owner/name' from SQLite. Never calls GitHub."""
    try:
        owner, name = parse_repo(repo)
        repository = f"{owner}/{name}".lower()

        conn = get_connection(db_path)
        try:
            cursor = conn.execute(
                "SELECT number, title, url FROM issues WHERE repository = ? ORDER BY number DESC",
                (repository,),
            )
            issues = [
                {"number": number, "title": title, "url": url}
                for number, title, url in cursor.fetchall()
            ]
        except sqlite3.Error as e:
            raise ConnectorError(f"Could not read issues: {e}") from e
        finally:
            conn.close()
    except ConnectorError as e:
        return {"ok": False, "error": str(e)}

    return {"ok": True, "repository": repository, "count": len(issues), "issues": issues}


def main():
    parser = argparse.ArgumentParser(description="GitHub issue snapshot connector")
    parser.add_argument("command", choices=["import", "read"], help="what to do")
    parser.add_argument("repo", help="repository as owner/name")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite database path")
    args = parser.parse_args()

    if args.command == "import":
        result = import_issues(args.repo, args.db)
    else:
        result = read_issues(args.repo, args.db)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()