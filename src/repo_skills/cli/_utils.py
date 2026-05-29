from __future__ import annotations

from rich.console import Console

from repo_skills.errors import AppError
from repo_skills.git import GitRepo
from repo_skills.utils import fmt_path

console = Console()


def echo(message: str, *, end: str = "\n") -> None:
    console.print(message, end=end)


def ensure_on_branch(git: GitRepo, branch: str, *, pull: bool = False) -> None:
    if not git.is_clean():
        raise AppError(
            "Repo has uncommitted changes.",
            props={"repo": fmt_path(git.root)},
        )

    if git.current_branch() != branch:
        git.checkout(branch)

    if pull:
        git.pull()
