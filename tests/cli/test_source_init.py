from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import SkillEntry as ManifestSkillEntry
from repo_skills.config import SkillManifest, SourceConfig, SourceRegistry
from tests.cli.helper import (
    SOURCE_CONFIG_DIR,
    SOURCE_REPO_ROOT,
    assert_invoke,
    assert_words_in_message,
    create_repo_skill,
)


class TestSourceInitFreshRepo:
    def test_creates_source_config_and_registers(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init")

        source_cfg = SourceConfig.load(git_repo / ".repo-skills" / "source.json")
        assert source_cfg.name == "my-project"
        assert source_cfg.skills_dir == "skills"

        assert (git_repo / "skills" / ".gitkeep").exists()

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / "sources.json")
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].path == str(SOURCE_REPO_ROOT)

        assert_words_in_message(result.output, "initialized", "source", "my-project")

        gitignore = git_repo / ".repo-skills" / ".gitignore"
        assert gitignore.exists()
        assert "*" in gitignore.read_text()


class TestSourceInitPopulatedRepo:
    def test_detects_existing_skills_dir(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "skills")

        assert_invoke("source", "init")

        source_cfg = SourceConfig.load(git_repo / ".repo-skills" / "source.json")
        assert source_cfg.skills_dir == "skills"
        assert not (git_repo / "skills" / ".gitkeep").exists()


class TestSourceInitNameOverride:
    def test_name_flag_overrides_derived_name(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init", "--name", "custom-name")

        source_cfg = SourceConfig.load(git_repo / ".repo-skills" / "source.json")
        assert source_cfg.name == "custom-name"

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / "sources.json")
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

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / "sources.json")
        registry.sources.pop("my-project", None)
        registry.save(SOURCE_CONFIG_DIR / "sources.json")

        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "registered", "my-project")

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / "sources.json")
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].path == str(SOURCE_REPO_ROOT)


@pytest.mark.usefixtures("git_repo")
class TestSourceInitRename:
    def test_rename_updates_config_and_registry(self) -> None:
        assert_invoke("source", "init", "--name", "old-name")
        result = assert_invoke("source", "init", "--name", "new-name")

        assert_words_in_message(result.output, "renamed", "old-name", "new-name")

        source_cfg = SourceConfig.load(
            SOURCE_REPO_ROOT / ".repo-skills" / "source.json"
        )
        assert source_cfg.name == "new-name"

        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / "sources.json")
        assert "new-name" in registry.sources
        assert "old-name" not in registry.sources
        assert registry.sources["new-name"].path == str(SOURCE_REPO_ROOT)

    def test_rename_blocked_by_installed_skills(self) -> None:
        assert_invoke("source", "init", "--name", "old-name")

        manifest = SkillManifest(skills={"tdd": ManifestSkillEntry(source="old-name")})
        manifest.save(SOURCE_CONFIG_DIR / "skill-manifest.json")

        result = assert_invoke(
            "source", "init", "--name", "new-name", expect_error=True
        )
        assert_words_in_message(result.exception.message, "not yet supported")


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

        source_cfg = SourceConfig.load(git_repo / ".repo-skills" / "source.json")
        assert source_cfg.skills_dir == "my-skills"

    def test_detects_skills_with_categories(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "skills" / "dev")
        create_repo_skill(fs, "deploy", root=git_repo / "skills" / "ops")

        assert_invoke("source", "init")

        source_cfg = SourceConfig.load(git_repo / ".repo-skills" / "source.json")
        assert source_cfg.skills_dir == "skills"
