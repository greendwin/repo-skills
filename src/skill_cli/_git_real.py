from __future__ import annotations

from pathlib import Path

from skill_cli._git import GitRepo


class RealGitRepo:
    def __init__(self, repo_path: Path) -> None:
        self._path = repo_path

    def pull(self) -> None:
        raise NotImplementedError

    def get_main_branch(self) -> str:
        raise NotImplementedError

    def current_branch(self) -> str:
        raise NotImplementedError

    def is_clean(self) -> bool:
        raise NotImplementedError

    def get_skill_commit(self, skill_name: str) -> str:
        raise NotImplementedError

    def verify_commit_content(self, commit: str, skill_name: str) -> bool:
        raise NotImplementedError


def _check_implements_protocol(_: GitRepo) -> None:
    pass


_check_implements_protocol(RealGitRepo(Path(".")))
