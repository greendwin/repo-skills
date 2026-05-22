from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import REPO_SKILLS_DIR as REPO_SKILLS_DIR_NAME
from repo_skills.config import (
    SKILL_MANIFEST_FILE,
    SOURCE_CONFIG_FILE,
    SOURCES_REGISTRY_FILE,
)
from repo_skills.config import SkillEntry as ManifestSkillEntry
from repo_skills.config import (
    SkillManifest,
    SourceConfig,
    SourceRegistry,
)
from tests.cli.helper import (
    SOURCE_CONFIG_DIR,
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_repo_skill,
)


class TestSourceInitFreshRepo:
    def test_creates_source_config_and_registers(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init")

        source_cfg = SourceConfig.load(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        assert source_cfg.name == "my-project"
        assert source_cfg.skills_dir == "skills"
        assert source_cfg.branch == "main"

        assert (git_repo / "skills" / ".gitkeep").exists()

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].path == str(SOURCE_REPO_ROOT)

        assert_words_in_message(result.output, "initialized", "source", "my-project")

        gitignore = git_repo / REPO_SKILLS_DIR_NAME / ".gitignore"
        assert gitignore.exists()
        assert "*" in gitignore.read_text()


class TestSourceInitPopulatedRepo:
    def test_detects_existing_skills_dir(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "skills")

        assert_invoke("source", "init")

        source_cfg = SourceConfig.load(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        assert source_cfg.skills_dir == "skills"
        assert not (git_repo / "skills" / ".gitkeep").exists()


class TestSourceInitBranch:
    def test_init_with_branch_flag(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branches = ["develop"]
        assert_invoke("source", "init", "--branch", "develop")

        source_cfg = SourceConfig.load(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
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

        source_cfg = SourceConfig.load(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        assert source_cfg.branch == "develop"

    def test_reinit_with_branch_updates_pin(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        assert_invoke("source", "init")

        _fake_git.branches = ["release"]
        assert_invoke("source", "init", "--branch", "release")

        source_cfg = SourceConfig.load(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        assert source_cfg.branch == "release"


class TestSourceInitNameOverride:
    def test_name_flag_overrides_derived_name(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init", "--name", "custom-name")

        source_cfg = SourceConfig.load(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        assert source_cfg.name == "custom-name"

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)
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

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)
        registry.sources.pop("my-project", None)
        registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)

        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "registered", "my-project")

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].path == str(SOURCE_REPO_ROOT)


@pytest.mark.usefixtures("git_repo")
class TestSourceInitRename:
    def test_rename_updates_config_and_registry(self) -> None:
        assert_invoke("source", "init", "--name", "old-name")
        result = assert_invoke("source", "init", "--name", "new-name")

        assert_words_in_message(result.output, "renamed", "old-name", "new-name")

        source_cfg = SourceConfig.load(
            SOURCE_REPO_ROOT / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        assert source_cfg.name == "new-name"

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)
        assert "new-name" in registry.sources
        assert "old-name" not in registry.sources
        assert registry.sources["new-name"].path == str(SOURCE_REPO_ROOT)

    def test_rename_updates_installed_skills_in_manifest(self) -> None:
        assert_invoke("source", "init", "--name", "old-name")

        manifest = SkillManifest(
            skills={
                "tdd": ManifestSkillEntry(source="old-name"),
                "review": ManifestSkillEntry(source="old-name"),
                "deploy": ManifestSkillEntry(source="other-source"),
            }
        )
        manifest.save(SOURCE_CONFIG_DIR / SKILL_MANIFEST_FILE)

        result = assert_invoke("source", "init", "--name", "new-name")
        assert_words_in_message(result.output, "renamed", "old-name", "new-name")

        updated = SkillManifest.load(SOURCE_CONFIG_DIR / SKILL_MANIFEST_FILE)
        assert updated.skills["tdd"].source == "new-name"
        assert updated.skills["review"].source == "new-name"
        assert updated.skills["deploy"].source == "other-source"


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

        source_cfg = SourceConfig.load(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        assert source_cfg.skills_dir == "my-skills"

    def test_detects_skills_with_categories(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "skills" / "dev")
        create_repo_skill(fs, "deploy", root=git_repo / "skills" / "ops")

        assert_invoke("source", "init")

        source_cfg = SourceConfig.load(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        assert source_cfg.skills_dir == "skills"
