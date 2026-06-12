from __future__ import annotations

import pytest

from repo_skills.console import console
from repo_skills.git import SyncedRepo, resolve_verified_commit
from tests.cli.helper import FakeGitRepo


def test_resolve_verified_commit_returns_commit_on_match() -> None:
    git = FakeGitRepo()
    git.branch_commits[("skills/tdd", "main")] = "deadbeef"

    assert resolve_verified_commit(SyncedRepo(git, "main"), "skills/tdd") == "deadbeef"


def test_resolve_verified_commit_returns_none_when_no_commit() -> None:
    git = FakeGitRepo()

    assert resolve_verified_commit(SyncedRepo(git, "main"), "skills/tdd") is None


def test_resolve_verified_commit_surfaces_swallowed_error_under_debug(
    capsys: pytest.CaptureFixture[str],
) -> None:
    git = FakeGitRepo()
    git.branch_commits[("skills/tdd", "main")] = "deadbeef"
    git.verified["skills/tdd"] = False

    console.debug = True
    try:
        result = resolve_verified_commit(SyncedRepo(git, "main"), "skills/tdd")
    finally:
        console.debug = False

    assert result is None
    captured = capsys.readouterr()
    assert "CommitVerificationError" in captured.err
