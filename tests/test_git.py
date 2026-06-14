from __future__ import annotations

import pytest

from repo_skills.git import (
    CommitVerificationError,
    SkillCommitNotFoundError,
    SyncedRepo,
    resolve_verified_commit,
)
from tests.cli.helper import FakeGitRepo


def test_resolve_verified_commit_returns_commit_on_match() -> None:
    git = FakeGitRepo()
    git.branch_commits[("skills/tdd", "main")] = "deadbeef"

    assert resolve_verified_commit(SyncedRepo(git, "main"), "skills/tdd") == "deadbeef"


def test_resolve_verified_commit_raises_when_no_commit() -> None:
    git = FakeGitRepo()

    with pytest.raises(SkillCommitNotFoundError) as ex:
        resolve_verified_commit(SyncedRepo(git, "main"), "skills/tdd")

    assert "No commit found" in ex.value.message
    assert "skills/tdd" in ex.value.message
    assert str(git.root) in ex.value.message


def test_resolve_verified_commit_propagates_verification_error() -> None:
    git = FakeGitRepo()
    git.branch_commits[("skills/tdd", "main")] = "deadbeef"
    git.verified["skills/tdd"] = False

    with pytest.raises(CommitVerificationError):
        resolve_verified_commit(SyncedRepo(git, "main"), "skills/tdd")
