from __future__ import annotations

import hashlib

import pytest
from cli_error import render_error

from repo_skills.git import (
    CommitVerificationError,
    SkillCommitNotFoundError,
    SyncedRepo,
    find_commit_with_content,
    resolve_verified_commit,
)
from repo_skills.utils import normalize_line_endings
from tests.cli.helper import FakeGitRepo


def _fingerprint(rel_path: str, files: dict[str, bytes]) -> dict[str, str]:
    result: dict[str, str] = {}
    for rel, raw in files.items():
        sha = hashlib.sha256(normalize_line_endings(raw)).hexdigest()
        result[rel] = f"sha256:{sha}"
    return result


def _seed_commit(
    git: FakeGitRepo, rel_path: str, commit: str, files: dict[str, str]
) -> None:
    for rel, content in files.items():
        git.files_at_commit[(commit, f"{rel_path}/{rel}")] = content.encode()


def test_find_commit_with_content_matches_head() -> None:
    git = FakeGitRepo()
    git.commit_logs["skills/tdd"] = ["head", "old"]
    _seed_commit(git, "skills/tdd", "head", {"SKILL.md": "# new"})
    _seed_commit(git, "skills/tdd", "old", {"SKILL.md": "# old"})

    target = _fingerprint("skills/tdd", {"SKILL.md": b"# new"})

    assert find_commit_with_content(git, "skills/tdd", target) == "head"


def test_find_commit_with_content_matches_deep_in_history() -> None:
    git = FakeGitRepo()
    git.commit_logs["skills/tdd"] = ["head", "mid", "old"]
    _seed_commit(git, "skills/tdd", "head", {"SKILL.md": "# new"})
    _seed_commit(git, "skills/tdd", "mid", {"SKILL.md": "# mid"})
    _seed_commit(git, "skills/tdd", "old", {"SKILL.md": "# wanted"})

    target = _fingerprint("skills/tdd", {"SKILL.md": b"# wanted"})

    assert find_commit_with_content(git, "skills/tdd", target) == "old"


def test_find_commit_with_content_no_match_returns_none() -> None:
    git = FakeGitRepo()
    git.commit_logs["skills/tdd"] = ["head", "old"]
    _seed_commit(git, "skills/tdd", "head", {"SKILL.md": "# a"})
    _seed_commit(git, "skills/tdd", "old", {"SKILL.md": "# b"})

    target = _fingerprint("skills/tdd", {"SKILL.md": b"# missing"})

    assert find_commit_with_content(git, "skills/tdd", target) is None


def test_find_commit_with_content_empty_history_returns_none() -> None:
    git = FakeGitRepo()

    target = _fingerprint("skills/tdd", {"SKILL.md": b"# anything"})

    assert find_commit_with_content(git, "skills/tdd", target) is None


def test_find_commit_with_content_extra_file_is_not_a_match() -> None:
    git = FakeGitRepo()
    git.commit_logs["skills/tdd"] = ["head"]
    _seed_commit(
        git, "skills/tdd", "head", {"SKILL.md": "# new", "extra.md": "# extra"}
    )

    target = _fingerprint("skills/tdd", {"SKILL.md": b"# new"})

    assert find_commit_with_content(git, "skills/tdd", target) is None


def test_find_commit_with_content_short_circuits_at_first_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git = FakeGitRepo()
    git.commit_logs["skills/tdd"] = ["head", "poison"]
    _seed_commit(git, "skills/tdd", "head", {"SKILL.md": "# new"})

    target = _fingerprint("skills/tdd", {"SKILL.md": b"# new"})

    original = git.get_file_at_commit

    def _poisoned(commit: str, path: str) -> bytes:
        if commit == "poison":
            raise AssertionError("must not hash commits past the first match")
        return original(commit, path)

    monkeypatch.setattr(git, "get_file_at_commit", _poisoned)

    assert find_commit_with_content(git, "skills/tdd", target) == "head"


def test_resolve_verified_commit_returns_commit_on_match() -> None:
    git = FakeGitRepo()
    git.branch_commits[("skills/tdd", "main")] = "deadbeef"

    assert resolve_verified_commit(SyncedRepo(git, "main"), "skills/tdd") == "deadbeef"


def test_resolve_verified_commit_raises_when_no_commit() -> None:
    git = FakeGitRepo()

    with pytest.raises(SkillCommitNotFoundError) as ex:
        resolve_verified_commit(SyncedRepo(git, "main"), "skills/tdd")

    rendered = render_error(ex.value.desc)
    assert "No commit found" in rendered
    assert "skills/tdd" in rendered
    assert str(git.root) in rendered


def test_resolve_verified_commit_propagates_verification_error() -> None:
    git = FakeGitRepo()
    git.branch_commits[("skills/tdd", "main")] = "deadbeef"
    git.verified["skills/tdd"] = False

    with pytest.raises(CommitVerificationError):
        resolve_verified_commit(SyncedRepo(git, "main"), "skills/tdd")
