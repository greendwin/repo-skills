from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, overload

from click.testing import Result
from pyfakefs.fake_filesystem import FakeFilesystem
from typer.testing import CliRunner

import repo_skills.cli._deps as deps_mod
from repo_skills.cli import app
from repo_skills.config import REPO_SKILLS_DIR as REPO_SKILLS_DIR_NAME
from repo_skills.config import (
    SKILL_MANIFEST_FILE,
    SOURCE_CONFIG_FILE,
    SOURCES_REGISTRY_FILE,
    SkillEntry,
    SkillManifest,
    SourceConfig,
    SourceEntry,
    SourceRegistry,
    compute_file_hashes,
)
from repo_skills.errors import AppError, NoopError


@dataclass
class NoopResult:
    output: str
    exit_code: int = 0


@dataclass
class ErrorResult:
    exception: AppError
    output: str


SOURCE_REPO_ROOT = Path("/repos/my-project")
SOURCE_CONFIG_DIR = Path("/home/user/.config/repo-skills")
REPO_SKILLS_DIR = Path("/repo/skills")
INSTALL_DIR = Path("/home/user/.claude/skills")
MANIFEST_PATH = INSTALL_DIR / ".skills-manifest.json"
SKILLS_DIR = SOURCE_REPO_ROOT / "skills"


@dataclass
class FakeGitRepo:
    path: Path = Path("/repos/my-project")
    main_branch: str = "main"
    branch: str = "main"
    clean: bool = True
    commits: dict[str, str] = field(default_factory=dict)
    verified: dict[str, bool] = field(default_factory=dict)
    pulled: bool = False
    created_branches: dict[str, str] = field(default_factory=dict)
    committed_messages: list[str] = field(default_factory=list)
    rebased_onto: str | None = None
    rebase_clean: bool = True
    rebasing: bool = False
    branches: list[str] = field(default_factory=list)
    deleted_branches: list[str] = field(default_factory=list)
    ff_targets: list[str] = field(default_factory=list)
    ff_fails: bool = False
    commit_logs: dict[str, list[str]] = field(default_factory=dict)
    files_at_commit: dict[tuple[str, str], bytes] = field(default_factory=dict)
    orphan_branches: list[str] = field(default_factory=list)
    rebase_root_clean: bool = True
    rebase_root_onto: str | None = None
    merge_clean: bool = True
    merged_branch: str | None = None
    merging: bool = False
    commit_messages: dict[str, str] = field(default_factory=dict)

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

    def log_commits(self, path: str, max_count: int) -> list[str]:
        return self.commit_logs.get(path, [])[:max_count]

    def get_file_at_commit(self, commit: str, path: str) -> bytes:
        return self.files_at_commit[(commit, path)]

    def create_branch(self, name: str, from_commit: str) -> None:
        self.created_branches[name] = from_commit
        self.branch = name

    def create_orphan_branch(self, name: str) -> None:
        self.orphan_branches.append(name)
        self.branch = name

    def checkout(self, branch: str) -> None:
        self.branch = branch

    def commit_all(self, message: str) -> None:
        self.committed_messages.append(message)

    def rebase(self, onto: str) -> bool:
        self.rebased_onto = onto
        return self.rebase_clean

    def rebase_root(self, onto: str) -> bool:
        self.rebase_root_onto = onto
        return self.rebase_root_clean

    def is_rebasing(self) -> bool:
        return self.rebasing

    def rebase_continue(self) -> None:
        self.rebasing = False

    def rebase_abort(self) -> None:
        self.rebasing = False

    def merge(self, branch: str) -> bool:
        self.merged_branch = branch
        return self.merge_clean

    def is_merging(self) -> bool:
        return self.merging

    def merge_abort(self) -> None:
        self.merging = False

    def fast_forward(self, branch: str) -> None:
        if self.ff_fails:
            raise AppError("Fast-forward failed.")
        self.ff_targets.append(branch)

    def delete_branch(self, name: str) -> None:
        self.deleted_branches.append(name)

    def get_commit_message(self, commit: str) -> str:
        return self.commit_messages.get(commit, "")

    def list_branches(self, pattern: str) -> list[str]:
        return [b for b in self.branches if pattern.rstrip("*") in b]


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
) -> Result | NoopResult: ...


def assert_invoke(
    *args: str,
    expect_error: bool = False,
) -> Result | ErrorResult | NoopResult:
    runner = CliRunner(env={"NO_COLOR": "1"})
    result = runner.invoke(app, args)

    if expect_error:
        assert isinstance(result.exception, AppError), (
            f"Expected AppError, got {result.exception!r}.\n" f"Output: {result.output}"
        )
        return ErrorResult(exception=result.exception, output=result.output)

    if isinstance(result.exception, NoopError):
        return NoopResult(output=result.exception.message)

    if result.exception is not None and not isinstance(result.exception, SystemExit):
        raise result.exception

    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}.\n"
        f"Output: {result.output}\n"
        f"Exception: {result.exception}"
    )
    return result


def assert_words_in_message(output: str, *words: str) -> None:
    lower = output.lower()
    for word in words:
        assert (
            word.lower() in lower
        ), f"Expected {word!r} in output (case-insensitive).\nOutput: {output}"


def _skill_md(name: str, description: str | None) -> str:
    if description:
        return f"---\nname: {name}\ndescription: {description}\n---\n"
    return f"# {name}"


def create_repo_skill(
    fs: FakeFilesystem,
    name: str,
    description: str | None = None,
    root: Path = REPO_SKILLS_DIR,
) -> Path:
    skill_dir = root / name
    fs.create_file(skill_dir / "SKILL.md", contents=_skill_md(name, description))
    return skill_dir


def create_installed_skill(
    fs: FakeFilesystem, name: str, description: str | None = None
) -> Path:
    skill_dir = INSTALL_DIR / name
    fs.create_file(skill_dir / "SKILL.md", contents=_skill_md(name, description))
    return skill_dir


def register_source(
    git_repo: Path,
    *,
    name: str = "my-project",
    skills_dir: str = "skills",
    branch: str = "",
) -> None:
    registry = SourceRegistry(sources={name: SourceEntry(path=str(git_repo))})
    registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)

    cfg = SourceConfig(name=name, skills_dir=skills_dir, branch=branch)
    cfg.save(git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE)


def save_manifest(skills: dict[str, SkillEntry]) -> None:
    manifest = SkillManifest(skills=skills)
    manifest.save(SOURCE_CONFIG_DIR / SKILL_MANIFEST_FILE)


def load_manifest() -> SkillManifest:
    return SkillManifest.load(SOURCE_CONFIG_DIR / SKILL_MANIFEST_FILE)


def install_skill(
    fs: FakeFilesystem,
    name: str,
    content: str = "# skill",
    *,
    install_dir: Path = INSTALL_DIR,
) -> dict[str, str]:
    skill_dir = install_dir / name
    fs.create_file(skill_dir / "SKILL.md", contents=content)
    return compute_file_hashes(skill_dir)


def create_source_skill(
    fs: FakeFilesystem,
    name: str,
    content: str = "# skill",
    *,
    root: Path = SKILLS_DIR,
) -> None:
    fs.create_file(root / name / "SKILL.md", contents=content)
