from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo_skills.errors import AppError
from repo_skills.git import CommitVerificationError
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
    git.verify_commit_content(commit, "skills/tdd")  # matches: does not raise


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
    with pytest.raises(CommitVerificationError) as exc:
        git.verify_commit_content(commit, "skills/tdd")
    assert exc.value.reason == "file 'skills/tdd/SKILL.md' differs"
    assert exc.value.file == "skills/tdd/SKILL.md"
    assert exc.value.repo == str(repo)


def test_verify_commit_content_missing_file(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# tdd")
    (skills_dir / "extra.md").write_text("# extra")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    commit = _git(repo, "log", "-1", "--format=%H")

    (skills_dir / "extra.md").unlink()

    git = RealGitRepo(repo)
    with pytest.raises(CommitVerificationError) as exc:
        git.verify_commit_content(commit, "skills/tdd")
    assert exc.value.reason == "missing file 'skills/tdd/extra.md'"
    assert exc.value.file == "skills/tdd/extra.md"
    assert exc.value.repo == str(repo)


def test_verify_commit_content_untracked_extra_file(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# tdd")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    commit = _git(repo, "log", "-1", "--format=%H")

    (skills_dir / "extra.md").write_text("# extra")

    git = RealGitRepo(repo)
    with pytest.raises(CommitVerificationError) as exc:
        git.verify_commit_content(commit, "skills/tdd")
    assert exc.value.reason == "untracked file 'skills/tdd/extra.md'"
    assert exc.value.file == "skills/tdd/extra.md"
    assert exc.value.repo == str(repo)


def test_verify_commit_content_reports_first_differing_file(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "a.md").write_text("# a")
    (skills_dir / "b.md").write_text("# b")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    commit = _git(repo, "log", "-1", "--format=%H")
    first = _git(
        repo, "ls-tree", "-r", "--name-only", commit, "skills/tdd"
    ).splitlines()[0]

    (skills_dir / "a.md").write_text("# a modified")
    (skills_dir / "b.md").write_text("# b modified")

    git = RealGitRepo(repo)
    with pytest.raises(CommitVerificationError) as exc:
        git.verify_commit_content(commit, "skills/tdd")
    assert exc.value.reason == f"file '{first}' differs"
    assert exc.value.file == first


def test_verify_commit_content_missing_wins_over_untracked(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "a.md").write_text("# a")
    (skills_dir / "b.md").write_text("# b")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    commit = _git(repo, "log", "-1", "--format=%H")

    (skills_dir / "a.md").unlink()
    (skills_dir / "extra.md").write_text("# extra")

    git = RealGitRepo(repo)
    with pytest.raises(CommitVerificationError) as exc:
        git.verify_commit_content(commit, "skills/tdd")
    assert exc.value.reason == "missing file 'skills/tdd/a.md'"
    assert exc.value.file == "skills/tdd/a.md"


def test_verify_commit_content_reports_first_untracked_file(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# tdd")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    commit = _git(repo, "log", "-1", "--format=%H")

    # Create the lexically-later file first to rule out discovery ordering.
    (skills_dir / "z-extra.md").write_text("# z")
    (skills_dir / "a-extra.md").write_text("# a")

    git = RealGitRepo(repo)
    with pytest.raises(CommitVerificationError) as exc:
        git.verify_commit_content(commit, "skills/tdd")
    assert exc.value.reason == "untracked file 'skills/tdd/a-extra.md'"
    assert exc.value.file == "skills/tdd/a-extra.md"


def test_verify_commit_content_not_present(repo: Path) -> None:
    commit = _git(repo, "log", "-1", "--format=%H")

    git = RealGitRepo(repo)
    with pytest.raises(CommitVerificationError) as exc:
        git.verify_commit_content(commit, "skills/missing")
    assert exc.value.reason is not None
    assert "skills/missing" in exc.value.reason
    assert "not present" in exc.value.reason
    assert exc.value.file is None
    assert exc.value.repo == str(repo)


def test_get_file_at_commit_normalizes_crlf(repo: Path) -> None:
    """get_file_at_commit returns LF-only bytes even when blob has CRLF."""
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_bytes(b"line1\r\nline2\r\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd with crlf")

    commit = _git(repo, "log", "-1", "--format=%H")

    git = RealGitRepo(repo)
    data = git.get_file_at_commit(commit, "skills/tdd/SKILL.md")
    assert b"\r\n" not in data
    assert data == b"line1\nline2\n"


def test_verify_commit_content_crlf_matches_lf(repo: Path) -> None:
    """CRLF local file should match LF content from git."""
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("line1\nline2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    commit = _git(repo, "log", "-1", "--format=%H")

    # Simulate Windows checkout: rewrite with CRLF
    (skills_dir / "SKILL.md").write_bytes(b"line1\r\nline2\r\n")

    git = RealGitRepo(repo)
    git.verify_commit_content(commit, "skills/tdd")  # matches: does not raise


def test_verify_commit_content_committed_crlf_matches_local_crlf(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Committed CRLF content should match local CRLF after normalization."""
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("line1\nline2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add tdd")

    commit = _git(repo, "log", "-1", "--format=%H")

    # Simulate Windows: local file has CRLF
    (skills_dir / "SKILL.md").write_bytes(b"line1\r\nline2\r\n")

    git = RealGitRepo(repo)

    # Patch _run_bytes to return CRLF content (simulating core.autocrlf=false)
    original_run_bytes = git._run_bytes

    def _crlf_run_bytes(*args: str) -> bytes:
        result = original_run_bytes(*args)
        # Inject CRLF into the committed content
        return result.replace(b"\n", b"\r\n")

    monkeypatch.setattr(git, "_run_bytes", _crlf_run_bytes)
    git.verify_commit_content(commit, "skills/tdd")  # matches: does not raise
