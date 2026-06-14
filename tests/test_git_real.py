from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from repo_skills.config import compute_file_hashes
from repo_skills.errors import AppError
from repo_skills.git import CommitVerificationError, find_commit_with_content
from repo_skills.git_real import RealGitRepo


def _fingerprint(content: bytes) -> dict[str, str]:
    sha = hashlib.sha256(content).hexdigest()
    return {"SKILL.md": f"sha256:{sha}"}


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


def test_find_commit_with_content_matches_head(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# v1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "v1")

    (skills_dir / "SKILL.md").write_text("# v2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "v2")
    head = _git(repo, "log", "-1", "--format=%H")

    target = _fingerprint(b"# v2\n")

    git = RealGitRepo(repo)
    assert find_commit_with_content(git, "skills/tdd", target) == head


def test_find_commit_with_content_matches_deep_in_history(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# wanted\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "v1")
    wanted = _git(repo, "log", "-1", "--format=%H")

    (skills_dir / "SKILL.md").write_text("# v2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "v2")

    target = _fingerprint(b"# wanted\n")

    git = RealGitRepo(repo)
    assert find_commit_with_content(git, "skills/tdd", target) == wanted


def test_find_commit_with_content_no_match_returns_none(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# v1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "v1")

    target = _fingerprint(b"# nowhere\n")

    git = RealGitRepo(repo)
    assert find_commit_with_content(git, "skills/tdd", target) is None


def test_find_commit_with_content_empty_history_returns_none(repo: Path) -> None:
    target = _fingerprint(b"# anything\n")

    git = RealGitRepo(repo)
    assert find_commit_with_content(git, "skills/missing", target) is None


def test_find_commit_with_content_returns_newest_matching_commit(repo: Path) -> None:
    """When identical content appears at two commits, the newer one wins."""
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)

    # Older commit holds the target content.
    (skills_dir / "SKILL.md").write_text("# X\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "x-old")
    older = _git(repo, "log", "-1", "--format=%H")

    # Change away from the target content.
    (skills_dir / "SKILL.md").write_text("# Y\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "y")

    # Newer commit restores the byte-identical target content.
    (skills_dir / "SKILL.md").write_text("# X\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "x-new")
    newer = _git(repo, "log", "-1", "--format=%H")

    target = _fingerprint(b"# X\n")

    git = RealGitRepo(repo)
    found = find_commit_with_content(git, "skills/tdd", target)
    assert found == newer
    assert found != older


def test_find_commit_with_content_extra_file_is_not_a_match(repo: Path) -> None:
    """A commit with an extra file beyond the target fingerprint is no match."""
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# only\n")
    (skills_dir / "extra.md").write_text("# extra\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "with extra")

    # Target fingerprint covers SKILL.md only (via the production hashing path).
    target = _fingerprint(b"# only\n")

    git = RealGitRepo(repo)
    assert find_commit_with_content(git, "skills/tdd", target) is None


def test_commit_content_hashes_maps_nested_files_relative_to_skill(
    repo: Path,
) -> None:
    skills_dir = repo / "skills" / "tdd"
    (skills_dir / "nested").mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# top\n")
    (skills_dir / "nested" / "more.md").write_text("# deep\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "multi")
    commit = _git(repo, "log", "-1", "--format=%H")

    git = RealGitRepo(repo)
    hashes = git.commit_content_hashes(commit, "skills/tdd")

    top = hashlib.sha256(b"# top\n").hexdigest()
    deep = hashlib.sha256(b"# deep\n").hexdigest()
    assert hashes == {
        "SKILL.md": f"sha256:{top}",
        "nested/more.md": f"sha256:{deep}",
    }


def test_commit_content_hashes_normalizes_crlf(repo: Path) -> None:
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_bytes(b"line1\r\nline2\r\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "crlf")
    commit = _git(repo, "log", "-1", "--format=%H")

    git = RealGitRepo(repo)
    hashes = git.commit_content_hashes(commit, "skills/tdd")

    normalized = hashlib.sha256(b"line1\nline2\n").hexdigest()
    assert hashes == {"SKILL.md": f"sha256:{normalized}"}


def test_commit_content_hashes_missing_skill_returns_empty(repo: Path) -> None:
    head = _git(repo, "log", "-1", "--format=%H")
    git = RealGitRepo(repo)
    assert git.commit_content_hashes(head, "skills/missing") == {}


def test_find_commit_with_content_crlf_fingerprint_matches_lf_commit(
    repo: Path, tmp_path: Path
) -> None:
    """A fingerprint hashed over CRLF bytes still finds the LF-committed blob."""
    skills_dir = repo / "skills" / "tdd"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("line1\nline2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "v1")
    wanted = _git(repo, "log", "-1", "--format=%H")

    # build the target via the production hashing path over CRLF bytes of the
    # same logical content; normalization parity must still match the LF commit
    work = tmp_path / "work" / "tdd"
    work.mkdir(parents=True)
    (work / "SKILL.md").write_bytes(b"line1\r\nline2\r\n")
    target = compute_file_hashes(work)

    git = RealGitRepo(repo)
    assert find_commit_with_content(git, "skills/tdd", target) == wanted


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
