from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, overload

from click.testing import Result
from pyfakefs.fake_filesystem import FakeFilesystem
from typer.testing import CliRunner

import repo_skills.cli._deps as deps_mod
from repo_skills.cli import app
from repo_skills.errors import AppError


@dataclass
class ErrorResult:
    exception: AppError
    output: str


REPO_SKILLS_DIR = Path("/repo/skills")
INSTALL_DIR = Path("/home/user/.claude/skills")
MANIFEST_PATH = INSTALL_DIR / ".skills-manifest.json"


@dataclass
class FakeGitRepo:
    main_branch: str = "main"
    branch: str = "main"
    clean: bool = True
    commits: dict[str, str] = field(default_factory=dict)
    verified: dict[str, bool] = field(default_factory=dict)
    pulled: bool = False

    def pull(self) -> None:
        self.pulled = True

    def get_main_branch(self) -> str:
        return self.main_branch

    def current_branch(self) -> str:
        return self.branch

    def is_clean(self) -> bool:
        return self.clean

    def get_skill_commit(self, skill_name: str) -> str:
        return self.commits.get(skill_name, "")

    def verify_commit_content(self, commit: str, skill_name: str) -> bool:
        return self.verified.get(skill_name, True)


def install_fake_git(fake: FakeGitRepo) -> None:
    deps_mod._git_repo_factory = lambda _path: fake


def uninstall_fake_git() -> None:
    deps_mod._git_repo_factory = None


@overload
def assert_invoke(
    *args: str,
    expect_error: Literal[True],
) -> ErrorResult: ...


@overload
def assert_invoke(
    *args: str,
    expect_error: Literal[False] = ...,
) -> Result: ...


def assert_invoke(
    *args: str,
    expect_error: bool = False,
) -> Result | ErrorResult:
    runner = CliRunner(env={"NO_COLOR": "1"})
    result = runner.invoke(app, args)

    if expect_error:
        assert isinstance(result.exception, AppError), (
            f"Expected AppError, got {result.exception!r}.\n" f"Output: {result.output}"
        )
        return ErrorResult(exception=result.exception, output=result.output)

    if result.exception is not None and not isinstance(result.exception, SystemExit):
        raise result.exception

    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}.\n"
        f"Output: {result.output}\n"
        f"Exception: {result.exception}"
    )
    return result


def _skill_md(name: str, description: str | None) -> str:
    if description:
        return f"---\nname: {name}\ndescription: {description}\n---\n"
    return f"# {name}"


def create_repo_skill(
    fs: FakeFilesystem, name: str, description: str | None = None
) -> Path:
    skill_dir = REPO_SKILLS_DIR / name
    fs.create_file(skill_dir / "SKILL.md", contents=_skill_md(name, description))
    return skill_dir


def create_installed_skill(
    fs: FakeFilesystem, name: str, description: str | None = None
) -> Path:
    skill_dir = INSTALL_DIR / name
    fs.create_file(skill_dir / "SKILL.md", contents=_skill_md(name, description))
    return skill_dir
