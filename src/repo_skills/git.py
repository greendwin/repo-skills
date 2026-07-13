from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from cli_error import CliError


@dataclass
class SyncedRepo:
    git: GitRepo
    branch: str


class GitCommandError(CliError):
    def __init__(self, message: str, stderr: str, /, **args: Any) -> None:
        super().__init__(message, **args)
        # raw, unescaped git stderr for control-flow matching (message/detail
        # are markup-escaped, so substring checks there are fragile)
        self.stderr = stderr
        if stderr:
            self.detail(stderr)


class FileNotInCommitError(CliError):
    def __init__(self, commit: str, path: str) -> None:
        self.commit = commit
        self.path = path
        super().__init__("File not found at commit")
        self.prop_id("commit", commit)
        self.prop_path("path", path)


class CommitVerificationError(CliError):
    def __init__(
        self, reason: str, *, repo_path: str, file_path: str | None = None
    ) -> None:
        super().__init__(reason)
        self.prop_path("repo", repo_path)
        if file_path is not None:
            self.prop_path("file", file_path)

        self.reason = reason
        self.repo = repo_path
        self.file = file_path


class SkillCommitNotFoundError(CliError):
    def __init__(self, *, repo_path: str, file_path: str) -> None:
        super().__init__("No commit found for skill content.")
        self.prop_path("repo", repo_path)
        self.prop_path("file", file_path)

        self.repo = repo_path
        self.file = file_path


class GitRepo(Protocol):
    @property
    def root(self) -> Path: ...
    def pull(self) -> None: ...
    def get_main_branch(self) -> str: ...
    def current_branch(self) -> str: ...
    def is_clean(self) -> bool: ...
    def get_skill_commit(self, rel_path: str, *, branch: str = "") -> str: ...
    def verify_commit_content(self, commit: str, rel_path: str) -> None: ...
    def log_commits(self, path: str, max_count: int | None = None) -> list[str]: ...
    def get_file_at_commit(self, commit: str, path: str) -> bytes: ...
    def commit_content_hashes(self, commit: str, rel_path: str) -> dict[str, str]: ...
    def create_branch(self, name: str, from_commit: str) -> None: ...
    def create_orphan_branch(self, name: str) -> None: ...
    def checkout(self, branch: str) -> None: ...
    def commit_all(self, message: str) -> None: ...
    def rebase(self, onto: str) -> bool: ...
    def rebase_root(self, onto: str) -> bool: ...
    def is_rebasing(self) -> bool: ...
    def rebase_continue(self) -> None: ...
    def rebase_abort(self) -> None: ...
    def merge(self, branch: str) -> bool: ...
    def is_merging(self) -> bool: ...
    def merge_abort(self) -> None: ...
    def fast_forward(self, branch: str) -> None: ...
    def delete_branch(self, name: str) -> None: ...
    def list_branches(self, pattern: str) -> list[str]: ...
    def get_commit_message(self, commit: str) -> str: ...
    def is_ancestor(self, commit: str, branch: str) -> bool: ...
    def commit_exists_in_any_branch(self, commit: str) -> bool: ...


def find_commit_with_content(
    git: GitRepo, rel_path: str, target_hashes: dict[str, str]
) -> str | None:
    for commit in git.log_commits(rel_path):
        if git.commit_content_hashes(commit, rel_path) == target_hashes:
            return commit

    return None


def resolve_verified_commit(
    repo: SyncedRepo,
    rel_path: str,
) -> str:
    commit = repo.git.get_skill_commit(rel_path, branch=repo.branch)
    if not commit:
        raise SkillCommitNotFoundError(repo_path=str(repo.git.root), file_path=rel_path)

    repo.git.verify_commit_content(commit, rel_path)

    return commit


def ensure_on_branch(
    git: GitRepo,
    branch: str,
    *,
    pull: bool = False,
    require_clean: bool = True,
) -> SyncedRepo:
    needs_checkout = git.current_branch() != branch

    # TODO: it's ok if it's not clean outside skill dirs and this does
    #       not prevent us from changing branch
    if require_clean or needs_checkout or pull:
        if not git.is_clean():
            raise CliError("Repo has uncommitted changes.").prop_path("repo", git.root)

    if needs_checkout:
        git.checkout(branch)

    if pull:
        git.pull()

    return SyncedRepo(git, branch)
