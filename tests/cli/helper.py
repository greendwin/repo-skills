from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, overload

from cli_error import CliError, CliExit, render_error
from pyfakefs.fake_filesystem import FakeFilesystem
from typer.testing import CliRunner

import repo_skills.cli._deps as deps_mod
from repo_skills.cli import app
from repo_skills.config import (
    Baseline,
    InstalledSkill,
    SkillManifest,
    SourceConfig,
    SourceRegistry,
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    save_provider_registry,
    save_skill_manifest,
    save_source_config,
    save_source_registry,
)
from repo_skills.git import CommitVerificationError, FileNotInCommitError
from repo_skills.utils import normalize_line_endings


@dataclass
class InvokeResult:
    output: str
    exit_code: int = 0


@dataclass
class NoopResult:
    output: str
    exit_code: int = 0


@dataclass
class ErrorResult:
    exception: CliError
    output: str
    # full rendered layout (message + props + detail + hint); props/hint are
    # NOT in str(exc), so substring assertions read this
    message: str


SOURCE_REPO_ROOT = Path("/repos/my-project")
SOURCE_CONFIG_DIR = Path("/home/user/.config/repo-skills")
INSTALL_DIR = Path("/home/user/.claude/skills")
MANIFEST_PATH = INSTALL_DIR / ".skills-manifest.json"
SKILLS_DIR = SOURCE_REPO_ROOT / "skills"


@dataclass
class FakeGitRepo:
    root: Path = field(default_factory=lambda: Path(SOURCE_REPO_ROOT))
    main_branch: str = "main"
    branch: str = "main"
    clean: bool = True
    pull_fails: bool = False
    pull_cause: str = ""
    commits: dict[str, str] = field(default_factory=dict)
    branch_commits: dict[tuple[str, str], str] = field(default_factory=dict)
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
    ancestors: dict[tuple[str, str], bool] = field(default_factory=dict)
    reachable_commits: set[str] = field(default_factory=set)

    def pull(self) -> None:
        if self.pull_fails:
            if self.pull_cause:
                try:
                    raise RuntimeError(self.pull_cause)
                except RuntimeError as inner:
                    raise CliError("Failed to pull from remote.").prop_path(
                        "repo", str(self.root)
                    ) from inner
            raise CliError("Failed to pull from remote.").prop_path(
                "repo", str(self.root)
            )
        self.pulled = True

    def get_main_branch(self) -> str:
        return self.main_branch

    def current_branch(self) -> str:
        return self.branch

    def is_clean(self) -> bool:
        return self.clean

    def get_skill_commit(self, rel_path: str, *, branch: str = "") -> str:
        if branch and (rel_path, branch) in self.branch_commits:
            return self.branch_commits[(rel_path, branch)]

        # once a branch is checked out, its skill commit matches HEAD's;
        # fall back to the branch-agnostic `commits` map
        return self.commits.get(rel_path, "")

    def verify_commit_content(self, commit: str, rel_path: str) -> None:
        if not self.verified.get(rel_path, True):
            raise CommitVerificationError("content mismatch", repo_path=str(self.root))

    def log_commits(self, path: str, max_count: int | None = None) -> list[str]:
        commits = self.commit_logs.get(path, [])
        if max_count is None:
            return list(commits)
        return commits[:max_count]

    def commit_content_hashes(self, commit: str, rel_path: str) -> dict[str, str]:
        prefix = f"{rel_path}/"
        paths = sorted(
            path
            for (c, path) in self.files_at_commit
            if c == commit and path.startswith(prefix)
        )
        hashes: dict[str, str] = {}
        for path in paths:
            raw = normalize_line_endings(self.get_file_at_commit(commit, path))
            sha = hashlib.sha256(raw).hexdigest()
            hashes[path[len(prefix) :]] = f"sha256:{sha}"
        return hashes

    def get_file_at_commit(self, commit: str, path: str) -> bytes:
        try:
            return self.files_at_commit[(commit, path)]
        except KeyError:
            raise FileNotInCommitError(commit, path) from None

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
            raise CliError("Fast-forward failed.")
        self.ff_targets.append(branch)

    def delete_branch(self, name: str) -> None:
        self.deleted_branches.append(name)

    def get_commit_message(self, commit: str) -> str:
        return self.commit_messages.get(commit, "")

    def is_ancestor(self, commit: str, branch: str) -> bool:
        return self.ancestors.get((commit, branch), False)

    def commit_exists_in_any_branch(self, commit: str) -> bool:
        return commit in self.reachable_commits

    def list_branches(self, pattern: str) -> list[str]:
        return [b for b in self.branches if pattern.rstrip("*") in b]


class FakeGitRepoManager:
    def __init__(self) -> None:
        self.repos: dict[str, FakeGitRepo] = {}

    def install(self, fake: FakeGitRepo) -> None:
        self.repos[str(fake.root)] = fake

    def uninstall_all(self) -> None:
        self.repos.clear()

    def make(self, root: Path) -> FakeGitRepo:
        key = str(root)
        existing = self.repos.get(key)
        if existing is not None:
            return existing

        created = FakeGitRepo(root=root)
        self.repos[key] = created
        return created


@overload
def assert_invoke(
    *args: str,
    expect_error: Literal[True],
) -> ErrorResult: ...


@overload
def assert_invoke(
    *args: str,
    expect_error: Literal[False] = ...,
) -> InvokeResult | NoopResult: ...


def assert_invoke(
    *args: str,
    expect_error: bool = False,
) -> InvokeResult | ErrorResult | NoopResult:
    runner = CliRunner(env={"NO_COLOR": "1"})
    result = runner.invoke(app, args)

    if expect_error:
        exc = result.exception
        assert isinstance(exc, CliError), (
            f"Expected CliError, got {exc!r}.\n" f"Output: {result.output}"
        )
        return ErrorResult(
            exception=exc,
            output=result.output,
            message=render_error(exc.desc),
        )

    if isinstance(result.exception, CliExit):
        output = result.output
        if output and not output.endswith("\n"):
            output += "\n"
        return NoopResult(output=output + result.exception.message)

    if result.exception is not None and not isinstance(result.exception, SystemExit):
        raise result.exception

    assert result.exit_code == 0, (
        f"Expected exit code 0, got {result.exit_code}.\n"
        f"Output: {result.output}\n"
        f"Exception: {result.exception}"
    )
    return InvokeResult(output=result.output, exit_code=result.exit_code)


def assert_words_in_message(output: str, *words: str) -> None:
    lower = output.lower()
    for word in words:
        assert (
            word.lower() in lower
        ), f"Expected {word!r} in output (case-insensitive).\nOutput: {output}"


def assert_status_line(
    output: str, prefix: str, suffix: str = "", *, present: bool = True
) -> None:
    """Assert a rendered ``"<prefix> ... <suffix>"`` status line in ``output``.

    With ``suffix=""`` the expected line is the bare terminated status
    ``"<prefix> ... "`` (the trailing space is load-bearing: it proves the
    in-place status line was flushed verbatim and un-clobbered; do not
    rstrip/strip it). A non-empty ``suffix`` yields ``"<prefix> ... <suffix>"``.
    Membership is checked against ``output.splitlines()``; ``present=False``
    asserts the line is absent.
    """
    line = f"{prefix} ... {suffix}" if suffix else f"{prefix} ... "
    lines = output.splitlines()
    if present:
        assert line in lines, f"Expected {line!r} in output.\nOutput: {output}"
    else:
        assert (
            line not in lines
        ), f"Did not expect {line!r} in output.\nOutput: {output}"


def _skill_md(name: str, description: str | None) -> str:
    if description:
        return f"---\nname: {name}\ndescription: {description}\n---\n"
    return f"# {name}"


def create_repo_skill(
    fs: FakeFilesystem,
    name: str,
    root: Path,
    description: str | None = None,
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


BROKEN_CONFIG_JSON = "{not valid json"


def write_broken_source(
    fs: FakeFilesystem,
    *,
    name: str = "broken-project",
    root: Path | None = None,
    registry: SourceRegistry | None = None,
) -> Path:
    """Create a broken source at ``root`` and register it.

    Writes ``root/.git`` and a malformed ``root/.repo-skills/source.json``
    (``BROKEN_CONFIG_JSON``), then registers ``name -> root``. Pass an existing
    ``registry`` to append to it (and save it) so multi-source tests can register
    several sources; otherwise a fresh single-source registry is saved.
    """
    root = Path("/repos/broken-project") if root is None else root
    fs.create_dir(root / ".git")
    fs.create_file(
        root / ".repo-skills" / "source.json",
        contents=BROKEN_CONFIG_JSON,
    )
    if registry is None:
        registry = SourceRegistry()
    registry.register_source(name, root)
    save_source_registry(registry)
    return root


def register_source(
    git_repo: Path,
    *,
    name: str = "my-project",
    skills_dir: str = "skills",
    skills_dirs: Sequence[str] | None = None,
    branch: str = "",
) -> SourceConfig:
    registry = SourceRegistry()
    registry.register_source(name, git_repo)
    save_source_registry(registry)

    dirs = list(skills_dirs) if skills_dirs is not None else [skills_dir]
    cfg = SourceConfig(name=name, skills_dirs=dirs, branch=branch)
    save_source_config(cfg, git_repo)

    return cfg


def register_two_sources(
    fs: FakeFilesystem,
    git_repo: Path,
    other_repo: Path,
    *,
    name: str = "my-project",
    other_name: str = "other-project",
) -> None:
    fs.create_dir(other_repo / ".git")

    registry = SourceRegistry()
    registry.register_source(name, git_repo)
    registry.register_source(other_name, other_repo)
    save_source_registry(registry)

    save_source_config(SourceConfig(name=name, skills_dirs=["skills"]), git_repo)
    save_source_config(
        SourceConfig(name=other_name, skills_dirs=["skills"]), other_repo
    )


def save_manifest(skills: dict[str, InstalledSkill]) -> None:
    manifest = SkillManifest()
    for name, entry in skills.items():
        manifest.register_skill(
            name,
            source_name=entry.source,
            baseline=entry.baseline,
            detached=entry.detached,
        )
    save_skill_manifest(manifest)


def load_manifest() -> SkillManifest:
    return load_skill_manifest()


def install_skill(
    fs: FakeFilesystem,
    name: str,
    content: str = "# skill",
    *,
    install_dir: Path | None = None,
) -> dict[str, str]:
    install_dir = Path(INSTALL_DIR) if install_dir is None else install_dir
    skill_dir = install_dir / name
    fs.create_file(skill_dir / "SKILL.md", contents=content)
    return compute_file_hashes(skill_dir)


def create_source_skill(
    fs: FakeFilesystem,
    name: str,
    content: str = "# skill",
    *,
    root: Path | None = None,
) -> None:
    root = Path(SKILLS_DIR) if root is None else root
    fs.create_file(root / name / "SKILL.md", contents=content)


def register_provider(name: str, install_dir: str) -> None:
    reg = load_provider_registry()
    reg.register(name, install_dir)
    save_provider_registry(reg)


OTHER_REPO_ROOT = Path("/repos/other-project")
OTHER_SKILLS_DIR = OTHER_REPO_ROOT / "skills"


@dataclass
class _SkillEntry:
    name: str
    source_name: str
    source_root: Path
    source_content: str
    installed_content: str
    commit: str
    detached: bool
    has_baseline: bool
    user_edited: str | None
    latest_commit: str | None


class SkillSetup:
    def __init__(self, fs: FakeFilesystem, git_repo: Path) -> None:
        self._fs = fs
        self._git_repo = git_repo
        self._entries: list[_SkillEntry] = []
        self._extra_sources: dict[str, Path] = {}

    def add_source(self, name: str, root: Path | None = None) -> SkillSetup:
        if root is None:
            root = self._git_repo
        self._extra_sources[name] = root
        return self

    def add_skill(
        self,
        name: str,
        *,
        source_content: str = "# skill",
        installed_content: str = "# skill",
        source_name: str = "my-project",
        source_root: Path | None = None,
        commit: str = "old",
        detached: bool = False,
        has_baseline: bool = True,
        user_edited: str | None = None,
        latest_commit: str | None = None,
    ) -> SkillSetup:
        if source_root is None:
            source_root = self._git_repo
        self._entries.append(
            _SkillEntry(
                name=name,
                source_name=source_name,
                source_root=source_root,
                source_content=source_content,
                installed_content=installed_content,
                commit=commit,
                detached=detached,
                has_baseline=has_baseline,
                user_edited=user_edited,
                latest_commit=latest_commit,
            )
        )
        return self

    def build(self) -> dict[str, dict[str, str]]:
        self._register_sources()

        hashes: dict[str, dict[str, str]] = {}
        manifest_skills: dict[str, InstalledSkill] = {}

        for entry in self._entries:
            skills_dir = entry.source_root / "skills"
            create_source_skill(
                self._fs,
                entry.name,
                content=entry.source_content,
                root=skills_dir,
            )
            h = install_skill(
                self._fs,
                entry.name,
                content=entry.installed_content,
            )
            hashes[entry.name] = h

            baseline = None
            if entry.has_baseline:
                baseline = Baseline(commit=entry.commit, files=h)

            manifest_skills[entry.name] = InstalledSkill(
                source=entry.source_name,
                baseline=baseline,
                detached=entry.detached,
            )

            if entry.user_edited is not None:
                (INSTALL_DIR / entry.name / "SKILL.md").write_text(entry.user_edited)

            if entry.latest_commit is not None:
                fake = self._fake_repo(entry.source_root)
                fake.branch_commits[(f"skills/{entry.name}", fake.main_branch)] = (
                    entry.latest_commit
                )

        save_manifest(manifest_skills)
        return hashes

    def _fake_repo(self, root: Path) -> FakeGitRepo:
        factory = deps_mod._git_repo_factory
        assert factory is not None, "fake_git_manager fixture is required"
        repo = factory(root)
        assert isinstance(repo, FakeGitRepo)
        return repo

    def _register_sources(self) -> None:
        seen: dict[str, Path] = {}
        for name, root in self._extra_sources.items():
            seen[name] = root
        for entry in self._entries:
            if entry.source_name in seen:
                continue
            seen[entry.source_name] = entry.source_root

        for root in seen.values():
            if not (root / ".git").exists():
                self._fs.create_dir(root / ".git")

        if len(seen) == 1:
            name, root = next(iter(seen.items()))
            register_source(root, name=name)
            return

        registry = SourceRegistry()
        for name, root in seen.items():
            registry.register_source(name, root)

        save_source_registry(registry)
        for name, root in seen.items():
            save_source_config(
                SourceConfig(name=name, skills_dirs=["skills"], branch=""),
                root,
            )
