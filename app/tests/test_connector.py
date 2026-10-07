import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import connector


class FakeResponse:
    """Stands in for the object requests.get() returns."""

    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def json(self):
        return self._payload


def make_issues():
    return [
        {"number": 1, "title": "First bug", "html_url": "https://github.com/o/r/issues/1"},
        {"number": 2, "title": "Second bug", "html_url": "https://github.com/o/r/issues/2"},
        # GitHub marks pull requests with a "pull_request" key; these must be skipped.
        {"number": 3, "title": "A pull request", "html_url": "https://github.com/o/r/pull/3",
         "pull_request": {}},
    ]


def mock_github(monkeypatch, response):
    monkeypatch.setattr(connector.requests, "get", lambda *args, **kwargs: response)


def count_rows(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    finally:
        conn.close()


def test_import_then_read(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    mock_github(monkeypatch, FakeResponse(200, make_issues()))

    result = connector.import_issues("O/R", db)
    assert result == {"ok": True, "repository": "o/r", "imported": 2}  # PR excluded

    saved = connector.read_issues("o/r", db)
    assert saved["ok"] is True
    assert saved["count"] == 2
    assert [i["number"] for i in saved["issues"]] == [2, 1]
    assert saved["issues"][0]["url"] == "https://github.com/o/r/issues/2"


def test_repeated_import_has_no_duplicates(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    mock_github(monkeypatch, FakeResponse(200, make_issues()))
    connector.import_issues("o/r", db)
    connector.import_issues("o/r", db)
    assert count_rows(db) == 2

    # A changed title on the second import should update the row, not add one.
    changed = make_issues()
    changed[0]["title"] = "First bug (renamed)"
    mock_github(monkeypatch, FakeResponse(200, changed))
    connector.import_issues("o/r", db)

    assert count_rows(db) == 2
    titles = [i["title"] for i in connector.read_issues("o/r", db)["issues"]]
    assert "First bug (renamed)" in titles



def test_api_failure_returns_error(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    mock_github(monkeypatch, FakeResponse(500))

    result = connector.import_issues("o/r", db)

    assert result["ok"] is False
    assert "500" in result["error"]
    assert connector.read_issues("o/r", db)["count"] == 0


def test_repository_not_found(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    mock_github(monkeypatch, FakeResponse(404))

    result = connector.import_issues("o/missing", db)

    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_network_failure(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")

    def offline(*args, **kwargs):
        raise connector.requests.exceptions.ConnectionError("no internet")

    monkeypatch.setattr(connector.requests, "get", offline)

    result = connector.import_issues("o/r", db)

    assert result["ok"] is False
    assert "Could not reach GitHub" in result["error"]


def test_failed_import_keeps_existing_data(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    mock_github(monkeypatch, FakeResponse(200, make_issues()))
    connector.import_issues("o/r", db)

    mock_github(monkeypatch, FakeResponse(500))
    assert connector.import_issues("o/r", db)["ok"] is False

    assert count_rows(db) == 2


def test_invalid_repository_never_calls_github(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")

    def should_not_be_called(*args, **kwargs):
        raise AssertionError("GitHub should not be called for an invalid repo")

    monkeypatch.setattr(connector.requests, "get", should_not_be_called)

    assert connector.import_issues("nonsense", db)["ok"] is False
    assert connector.read_issues("nonsense", db)["ok"] is False