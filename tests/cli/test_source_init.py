from __future__ import annotations

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

    def test_branch_flag_errors_when_branch_missing(
        self, git_repo: Path, _fake_git: FakeGitRepo
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


class TestInitRedirect:
    def test_init_shows_redirect_to_source_init(self) -> None:
        result = assert_invoke("init", expect_error=True)
        assert_words_in_message(result.exception.message, "source init")

    def test_init_hidden_from_help(self) -> None:
        result = assert_invoke("--help")
        assert "init" not in result.output.lower()


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


class TestSourceInitBrokenSourceRegistry:
    def test_broken_registry_warns_and_initializes(self, git_repo: Path) -> None:
        source_path = default_config_path(SOURCES_REGISTRY_FILE)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("{{{invalid")

        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "warning", "broken config file")
        assert_words_in_message(result.output, "initialized", "my-project")

        registry = load_source_registry()
        assert "my-project" in registry.sources
