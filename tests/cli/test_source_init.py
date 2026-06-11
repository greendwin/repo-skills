from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    REPO_SKILLS_DIR,
    InstalledSkill,
    default_config_path,
    load_source_config,
    load_source_registry,
    save_source_registry,
)
from repo_skills.config._source_registry import SOURCES_REGISTRY_FILE
from tests.cli.helper import (
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_repo_skill,
    load_manifest,
    save_manifest,
)


def _help_command_names(output: str) -> set[str]:
    """Extract the command-name column from a Typer ``--help`` Commands panel.

    Rich renders commands in a bordered panel; a command row places its name in a
    fixed left column right after ``│ `` while wrapped description lines indent
    their text further. Anchoring to that column (a non-space immediately after
    the border) avoids matching description prose or substrings elsewhere.
    """
    names: set[str] = set()
    in_commands = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("╭─") and "Commands" in stripped:
            in_commands = True
            continue
        if in_commands and stripped.startswith("╰"):
            break
        if in_commands and stripped.startswith("│"):
            row = stripped[1:]
            if row.startswith(" ") and not row[1:2].isspace():
                names.add(row.split()[0])
    return names


class TestSourceInitFreshRepo:
    def test_creates_source_config_and_registers(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.name == "my-project"
        assert source_cfg.skills_dir == "skills"
        assert source_cfg.branch == "main"

        assert (git_repo / "skills" / ".gitkeep").exists()

        registry = load_source_registry()
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].repo_root == Path(str(SOURCE_REPO_ROOT))

        assert_words_in_message(result.output, "initialized", "source", "my-project")

        gitignore = git_repo / REPO_SKILLS_DIR / ".gitignore"
        assert gitignore.exists()
        assert "*" in gitignore.read_text()


class TestSourceInitPopulatedRepo:
    def test_detects_existing_skills_dir(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "skills")

        assert_invoke("source", "init")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.skills_dir == "skills"
        assert not (git_repo / "skills" / ".gitkeep").exists()


class TestSourceInitBranch:
    def test_init_with_branch_flag(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branches = ["develop"]
        assert_invoke("source", "init", "--branch", "develop")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.branch == "develop"

    @pytest.mark.usefixtures("git_repo")
    def test_branch_flag_errors_when_branch_missing(
        self, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branches = []
        result = assert_invoke(
            "source", "init", "--branch", "no-such", expect_error=True
        )
        assert_words_in_message(result.exception.message, "no-such", "not found")

    def test_reinit_preserves_existing_branch(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branches = ["develop"]
        assert_invoke("source", "init", "--branch", "develop")

        _fake_git.branch = "feature/xyz"
        assert_invoke("source", "init")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.branch == "develop"

    def test_reinit_with_branch_updates_pin(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        assert_invoke("source", "init")

        _fake_git.branches = ["release"]
        result = assert_invoke("source", "init", "--branch", "release")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.branch == "release"

        assert_words_in_message(result.output, "updated", "my-project")
        assert "branch:" in result.output.lower()
        assert "main" in result.output
        assert "release" in result.output


class TestSourceInitNameOverride:
    def test_name_flag_overrides_derived_name(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init", "--name", "custom-name")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.name == "custom-name"

        registry = load_source_registry()
        assert "custom-name" in registry.sources
        assert "my-project" not in registry.sources

        assert_words_in_message(result.output, "initialized", "source", "custom-name")


@pytest.mark.usefixtures("git_repo")
class TestSourceInitIdempotent:
    def test_already_initialized_is_not_error(self) -> None:
        assert_invoke("source", "init")
        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "already initialized", "my-project")

    def test_already_initialized_with_matching_name(self) -> None:
        assert_invoke("source", "init", "--name", "custom")
        result = assert_invoke("source", "init", "--name", "custom")

        assert_words_in_message(result.output, "already initialized", "custom")

    def test_reinit_re_registers_removed_source(self) -> None:
        assert_invoke("source", "init")

        registry = load_source_registry()
        registry.unregister_source("my-project")
        save_source_registry(registry)

        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "registered", "my-project")

        registry = load_source_registry()
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].repo_root == Path(str(SOURCE_REPO_ROOT))

    def test_re_register_with_branch_change(self, _fake_git: FakeGitRepo) -> None:
        assert_invoke("source", "init")

        registry = load_source_registry()
        registry.unregister_source("my-project")
        save_source_registry(registry)

        _fake_git.branches = ["release"]
        result = assert_invoke("source", "init", "--branch", "release")

        assert_words_in_message(result.output, "registered", "my-project")
        assert "branch:" in result.output.lower()
        assert "release" in result.output


@pytest.mark.usefixtures("git_repo")
class TestSourceInitRename:
    def test_rename_updates_config_and_registry(self) -> None:
        assert_invoke("source", "init", "--name", "old-name")
        result = assert_invoke("source", "init", "--name", "new-name")

        assert_words_in_message(result.output, "updated", "new-name")
        assert "name:" in result.output.lower()
        assert "old-name" in result.output
        assert "new-name" in result.output

        source_cfg = load_source_config(SOURCE_REPO_ROOT)
        assert source_cfg is not None
        assert source_cfg.name == "new-name"

        registry = load_source_registry()
        assert "new-name" in registry.sources
        assert "old-name" not in registry.sources
        assert registry.sources["new-name"].repo_root == Path(str(SOURCE_REPO_ROOT))

    def test_rename_with_branch_change_shows_both(self, _fake_git: FakeGitRepo) -> None:
        assert_invoke("source", "init", "--name", "old-name")

        _fake_git.branches = ["develop"]
        result = assert_invoke(
            "source", "init", "--name", "new-name", "--branch", "develop"
        )

        assert_words_in_message(result.output, "updated", "new-name")
        assert "name:" in result.output.lower()
        assert "branch:" in result.output.lower()
        assert "old-name" in result.output
        assert "new-name" in result.output
        assert "develop" in result.output

    def test_rename_updates_installed_skills_in_manifest(self) -> None:
        assert_invoke("source", "init", "--name", "old-name")

        save_manifest(
            {
                "tdd": InstalledSkill(source="old-name"),
                "review": InstalledSkill(source="old-name"),
                "deploy": InstalledSkill(source="other-source"),
            }
        )

        result = assert_invoke("source", "init", "--name", "new-name")
        assert_words_in_message(result.output, "updated", "new-name")

        updated = load_manifest()
        assert updated.skills["tdd"].source == "new-name"
        assert updated.skills["review"].source == "new-name"
        assert updated.skills["deploy"].source == "other-source"


class TestTopLevelInit:
    def test_creates_source_config_and_registers(self, git_repo: Path) -> None:
        result = assert_invoke("init")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.name == "my-project"
        assert source_cfg.skills_dir == "skills"
        assert source_cfg.branch == "main"

        assert (git_repo / "skills" / ".gitkeep").exists()

        registry = load_source_registry()
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].repo_root == Path(str(SOURCE_REPO_ROOT))

        assert_words_in_message(result.output, "initialized", "source", "my-project")

    def test_init_is_visible_in_top_level_help(self) -> None:
        result = assert_invoke("--help")
        assert "init" in _help_command_names(result.output)


class TestSourceConfig:
    def test_fresh_repo_creates_and_registers(self, git_repo: Path) -> None:
        result = assert_invoke("source", "config")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.name == "my-project"

        registry = load_source_registry()
        assert "my-project" in registry.sources

        assert_words_in_message(result.output, "initialized", "source", "my-project")

    def test_existing_source_edits_branch(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        assert_invoke("source", "config")

        _fake_git.branches = ["release"]
        result = assert_invoke("source", "config", "--branch", "release")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.branch == "release"

        assert_words_in_message(result.output, "updated", "my-project")

    @pytest.mark.usefixtures("git_repo")
    def test_config_is_visible_in_source_help(self) -> None:
        result = assert_invoke("source", "--help")
        assert "config" in _help_command_names(result.output)


class TestSourceInitAlias:
    def test_hidden_alias_still_works(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.name == "my-project"

        assert_words_in_message(result.output, "initialized", "source", "my-project")

    @pytest.mark.usefixtures("git_repo")
    def test_init_is_hidden_from_source_help(self) -> None:
        result = assert_invoke("source", "--help")
        assert "init" not in _help_command_names(result.output)


class TestSourceInitErrors:
    def test_not_in_git_repo(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fs.create_dir("/not-a-repo")
        monkeypatch.chdir("/not-a-repo")

        result = assert_invoke("source", "init", expect_error=True)
        assert_words_in_message(result.exception.message, "git")


class TestSourceInitAutoDetect:
    def test_detects_skills_in_subdirectory(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "my-skills")
        create_repo_skill(fs, "review", root=git_repo / "my-skills")

        assert_invoke("source", "init")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.skills_dir == "my-skills"

    def test_detects_skills_with_categories(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "skills" / "dev")
        create_repo_skill(fs, "deploy", root=git_repo / "skills" / "ops")

        assert_invoke("source", "init")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.skills_dir == "skills"


class TestSourceInitSkillsDir:
    def test_fresh_init_with_skills_dir_uses_it_and_skips_bootstrap(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "my-skills")

        result = assert_invoke("source", "init", "--skills-dir", "my-skills")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.name == "my-project"
        assert source_cfg.skills_dir == "my-skills"
        assert source_cfg.branch == "main"

        assert not (git_repo / "skills").exists()
        assert not (git_repo / "my-skills" / ".gitkeep").exists()

        registry = load_source_registry()
        assert "my-project" in registry.sources

        gitignore = git_repo / REPO_SKILLS_DIR / ".gitignore"
        assert gitignore.exists()
        assert "*" in gitignore.read_text()

        assert_words_in_message(result.output, "initialized", "my-project")

    def test_skills_dir_overrides_auto_detection(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "auto-skills")
        fs.create_dir(git_repo / "chosen-skills")

        assert_invoke("source", "init", "--skills-dir", "chosen-skills")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.skills_dir == "chosen-skills"

    def test_skills_dir_is_normalized_before_storing(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "my-skills")

        assert_invoke("source", "init", "--skills-dir", "./my-skills/")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.skills_dir == "my-skills"

    def test_explicit_default_name_still_requires_existing_dir(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        result = assert_invoke(
            "source", "init", "--skills-dir", "skills", expect_error=True
        )

        assert_words_in_message(
            result.exception.message, "Skills dir", "skills", "not found"
        )
        assert not (git_repo / "skills").exists()

    def test_reinit_with_skills_dir_updates_value_and_emits_change(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        assert_invoke("source", "init")
        fs.create_dir(git_repo / "new-skills")

        result = assert_invoke("source", "init", "--skills-dir", "new-skills")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.skills_dir == "new-skills"

        assert_words_in_message(
            result.output, "updated", "skills_dir", "skills", "new-skills"
        )

    def test_reinit_with_name_branch_and_skills_dir_together(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        assert_invoke("source", "init", "--name", "old-name")

        fs.create_dir(git_repo / "new-skills")
        _fake_git.branches = ["develop"]

        result = assert_invoke(
            "source",
            "init",
            "--name",
            "new-name",
            "--branch",
            "develop",
            "--skills-dir",
            "new-skills",
        )

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.name == "new-name"
        assert source_cfg.branch == "develop"
        assert source_cfg.skills_dir == "new-skills"

        registry = load_source_registry()
        assert "new-name" in registry.sources
        assert "old-name" not in registry.sources

        assert_words_in_message(result.output, "updated", "new-name")
        assert "name:" in result.output.lower()
        assert "branch:" in result.output.lower()
        assert "skills_dir:" in result.output.lower()

    def test_reinit_with_same_skills_dir_emits_no_change(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        assert_invoke("source", "init")

        result = assert_invoke("source", "init", "--skills-dir", "skills")

        assert_words_in_message(result.output, "already initialized", "my-project")
        assert "skills_dir:" not in result.output

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.skills_dir == "skills"

    @pytest.mark.parametrize(
        ("skills_dir", "setup", "extra_words"),
        [
            pytest.param("missing", lambda fs: None, ("missing",), id="non-existent"),
            pytest.param(
                "/elsewhere",
                lambda fs: fs.create_dir("/elsewhere"),
                ("/elsewhere",),
                id="absolute",
            ),
            pytest.param(
                "../sibling",
                lambda fs: fs.create_dir("/repos/sibling"),
                ("../sibling",),
                id="escaping",
            ),
            pytest.param(
                "not-a-dir.txt",
                lambda fs: fs.create_file(
                    SOURCE_REPO_ROOT / "not-a-dir.txt", contents=""
                ),
                ("not-a-dir.txt",),
                id="path-is-file",
            ),
            pytest.param(".", lambda fs: None, (), id="repo-root"),
        ],
    )
    @pytest.mark.usefixtures("git_repo")
    def test_error_invalid_skills_dir(
        self,
        fs: FakeFilesystem,
        skills_dir: str,
        setup: Callable[[FakeFilesystem], object],
        extra_words: tuple[str, ...],
    ) -> None:
        setup(fs)

        result = assert_invoke(
            "source", "init", "--skills-dir", skills_dir, expect_error=True
        )

        assert_words_in_message(
            result.exception.message, "Skills dir", "not found", *extra_words
        )


VISIBLE_COMMAND_PREFIXES = [
    pytest.param(("init",), id="init"),
    pytest.param(("source", "config"), id="source-config"),
    pytest.param(("source", "init"), id="source-init-alias"),
]


class TestCommandSurface:
    """Each command surface (``init``, ``source config``, hidden ``source init``)
    shares one option declaration via ``Depends``; prove every surface reaches
    create-or-edit and accepts ``--skills-dir``.
    """

    @pytest.mark.parametrize("prefix", VISIBLE_COMMAND_PREFIXES)
    def test_fresh_create_with_skills_dir(
        self, fs: FakeFilesystem, git_repo: Path, prefix: tuple[str, ...]
    ) -> None:
        fs.create_dir(git_repo / "my-skills")

        result = assert_invoke(*prefix, "--skills-dir", "my-skills")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.skills_dir == "my-skills"

        assert_words_in_message(result.output, "initialized", "my-project")

    @pytest.mark.parametrize("prefix", VISIBLE_COMMAND_PREFIXES)
    def test_edit_existing_source_updates_branch(
        self, git_repo: Path, _fake_git: FakeGitRepo, prefix: tuple[str, ...]
    ) -> None:
        assert_invoke(*prefix)

        _fake_git.branches = ["release"]
        result = assert_invoke(*prefix, "--branch", "release")

        source_cfg = load_source_config(git_repo)
        assert source_cfg is not None
        assert source_cfg.branch == "release"

        assert_words_in_message(result.output, "updated", "my-project")


class TestSourceInitBrokenSourceRegistry:
    @pytest.mark.usefixtures("git_repo")
    def test_broken_registry_warns_and_initializes(self) -> None:
        source_path = default_config_path(SOURCES_REGISTRY_FILE)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("{{{invalid")

        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "warning", "broken config file")
        assert_words_in_message(result.output, "initialized", "my-project")

        registry = load_source_registry()
        assert "my-project" in registry.sources
