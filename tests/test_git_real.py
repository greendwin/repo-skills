from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo_skills.errors import AppError
from repo_skills.git_real import RealGitRepo


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", str(tmp_path))
    _git(tmp_path, "checkout", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@test.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("init")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    return tmp_path


def test_current_branch(repo: Path) -> None:
    git = RealGitRepo(repo)
    assert git.current_branch() == "main"


def test_is_clean_on_clean_repo(repo: Path) -> None:
    git = RealGitRepo(repo)
    assert git.is_clean() is True


def test_is_clean_on_dirty_repo(repo: Path) -> None:
    (repo / "dirty.txt").write_text("dirty")
    git = RealGitRepo(repo)
    assert git.is_clean() is False


def test_get_main_branch_fallback(repo: Path) -> None:
    git = RealGitRepo(repo)
    assert git.get_main_branch() == "main"


def test_get_main_branch_from_origin(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(tmp_path, "init", "--bare", str(origin))

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(origin), str(clone))
    _git(clone, "config", "user.email", "test@test.com")
    _git(clone, "config", "user.name", "Test")
    _git(clone, "checkout", "-b", "trunk")
    (clone / "f.txt").write_text("x")
    _git(clone, "add", ".")
    _git(clone, "commit", "-m", "init")
    _git(clone, "push", "-u", "origin", "trunk")
    _git(clone, "remote", "set-head", "origin", "trunk")

    git = RealGitRepo(clone)
    assert git.get_main_branch() == "trunk"


def test_pull_fetches_new_commits(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    clone = tmp_path / "clone"

    _git(tmp_path, "init", str(origin))
    _git(origin, "config", "user.email", "test@test.com")
    _git(origin, "config", "user.name", "Test")
    (origin / "f.txt").write_text("x")
    _git(origin, "add", ".")
    _git(origin, "commit", "-m", "first")

    _git(tmp_path, "clone", str(origin), str(clone))

    (origin / "f.txt").write_text("updated")
    _git(origin, "add", ".")
    _git(origin, "commit", "-m", "second")

    git = RealGitRepo(clone)
    git.pull()

    assert (clone / "f.txt").read_text() == "updated"


def test_pull_falls_back_when_no_tracking(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    clone = tmp_path / "clone"

    _git(tmp_path, "init", str(origin))
    _git(origin, "config", "user.email", "test@test.com")
    _git(origin, "config", "user.name", "Test")
    _git(origin, "checkout", "-b", "main")
    (origin / "f.txt").write_text("x")
    _git(origin, "add", ".")
    _git(origin, "commit", "-m", "first")

    _git(tmp_path, "clone", str(origin), str(clone))
    _git(clone, "branch", "--unset-upstream")

    (origin / "f.txt").write_text("updated")
    _git(origin, "add", ".")
    _git(origin, "commit", "-m", "second")

    git = RealGitRepo(clone)
    git.pull()

    assert (clone / "f.txt").read_text() == "updated"


def test_git_error_includes_repo_path(repo: Path) -> None:
    git = RealGitRepo(repo)
    with pytest.raises(AppError, match=str(repo)):
        git._run("log", "--bad-flag")


def test_get_skill_commit(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# tdd")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    expected = _git(repo, "log", "-1", "--format=%H", "--", "skills/tdd")

    git = RealGitRepo(repo)
    assert git.get_skill_commit("skills/tdd") == expected
    assert len(expected) == 40


def test_verify_commit_content_matches(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# tdd")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    commit = _git(repo, "log", "-1", "--format=%H")

    git = RealGitRepo(repo)
    assert git.verify_commit_content(commit, "skills/tdd") is True


def test_is_ancestor_true_when_reachable(repo: Path) -> None:
    (repo / "f.txt").write_text("change")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "second")
    ancestor = _git(repo, "log", "-1", "--format=%H", "HEAD~1")

    git = RealGitRepo(repo)
    assert git.is_ancestor(ancestor, "main") is True


def test_is_ancestor_false_when_unreachable(repo: Path) -> None:
    _git(repo, "checkout", "-b", "other")
    (repo / "other.txt").write_text("other")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "other branch")
    other_commit = _git(repo, "log", "-1", "--format=%H")
    _git(repo, "checkout", "main")

    git = RealGitRepo(repo)
    assert git.is_ancestor(other_commit, "main") is False


def test_commit_exists_in_any_branch_true(repo: Path) -> None:
    commit = _git(repo, "log", "-1", "--format=%H")

    git = RealGitRepo(repo)
    assert git.commit_exists_in_any_branch(commit) is True


def test_commit_exists_in_any_branch_false_when_dangling(repo: Path) -> None:
    (repo / "f.txt").write_text("extra")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "extra")
    dangling = _git(repo, "log", "-1", "--format=%H")
    _git(repo, "reset", "--hard", "HEAD~1")

    git = RealGitRepo(repo)
    assert git.commit_exists_in_any_branch(dangling) is False


def test_verify_commit_content_mismatch(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# tdd")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    commit = _git(repo, "log", "-1", "--format=%H")

    (skills_dir / "SKILL.md").write_text("# tdd modified")

    git = RealGitRepo(repo)
    assert git.verify_commit_content(commit, "skills/tdd") is False
