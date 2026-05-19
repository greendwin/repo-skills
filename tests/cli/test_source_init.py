from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills._config import SkillEntry as ManifestSkillEntry
from repo_skills._config import SkillManifest, SourceConfig, SourceRegistry
from tests.cli.helper import assert_invoke, assert_words_in_message

REPO_ROOT = Path("/repos/my-project")
CONFIG_DIR = Path("/home/user/.config/repo-skills")


def _make_git_repo(fs: FakeFilesystem, root: Path = REPO_ROOT) -> None:
    fs.create_dir(root / ".git")


class TestSourceInitFreshRepo:
    def test_creates_source_config_and_registers(
        self, fs: FakeFilesystem, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        monkeypatch.chdir(REPO_ROOT)

        result = assert_invoke("source", "init")

        source_cfg = SourceConfig.load(REPO_ROOT / ".repo-skills" / "source.json")
        assert source_cfg.name == "my-project"
        assert source_cfg.skills_dir == "skills"

        assert (REPO_ROOT / "skills" / ".gitkeep").exists()

        registry = SourceRegistry.load(CONFIG_DIR / "sources.json")
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].path == str(REPO_ROOT)

        assert_words_in_message(result.output, "initialized", "source", "my-project")

        gitignore = REPO_ROOT / ".repo-skills" / ".gitignore"
        assert gitignore.exists()
        assert "source.json" in gitignore.read_text()


class TestSourceInitPopulatedRepo:
    def test_detects_existing_skills_dir(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        fs.create_file(REPO_ROOT / "skills" / "tdd" / "SKILL.md", contents="# TDD")
        monkeypatch.chdir(REPO_ROOT)

        assert_invoke("source", "init")

        source_cfg = SourceConfig.load(REPO_ROOT / ".repo-skills" / "source.json")
        assert source_cfg.skills_dir == "skills"
        assert not (REPO_ROOT / "skills" / ".gitkeep").exists()


class TestSourceInitNameOverride:
    def test_name_flag_overrides_derived_name(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        monkeypatch.chdir(REPO_ROOT)

        result = assert_invoke("source", "init", "--name", "custom-name")

        source_cfg = SourceConfig.load(REPO_ROOT / ".repo-skills" / "source.json")
        assert source_cfg.name == "custom-name"

        registry = SourceRegistry.load(CONFIG_DIR / "sources.json")
        assert "custom-name" in registry.sources
        assert "my-project" not in registry.sources

        assert_words_in_message(result.output, "initialized", "source", "custom-name")


class TestSourceInitIdempotent:
    def test_already_initialized_is_not_error(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        monkeypatch.chdir(REPO_ROOT)

        assert_invoke("source", "init")
        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "already initialized", "my-project")

    def test_already_initialized_with_matching_name(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        monkeypatch.chdir(REPO_ROOT)

        assert_invoke("source", "init", "--name", "custom")
        result = assert_invoke("source", "init", "--name", "custom")

        assert_words_in_message(result.output, "already initialized", "custom")


class TestSourceInitRename:
    def test_rename_updates_config_and_registry(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        monkeypatch.chdir(REPO_ROOT)

        assert_invoke("source", "init", "--name", "old-name")
        result = assert_invoke("source", "init", "--name", "new-name")

        assert_words_in_message(result.output, "renamed", "old-name", "new-name")

        source_cfg = SourceConfig.load(REPO_ROOT / ".repo-skills" / "source.json")
        assert source_cfg.name == "new-name"

        registry = SourceRegistry.load(CONFIG_DIR / "sources.json")
        assert "new-name" in registry.sources
        assert "old-name" not in registry.sources
        assert registry.sources["new-name"].path == str(REPO_ROOT)

    def test_rename_blocked_by_installed_skills(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        monkeypatch.chdir(REPO_ROOT)

        assert_invoke("source", "init", "--name", "old-name")

        manifest = SkillManifest(skills={"tdd": ManifestSkillEntry(source="old-name")})
        manifest.save(CONFIG_DIR / "skill-manifest.json")

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
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        fs.create_file(REPO_ROOT / "my-skills" / "tdd" / "SKILL.md", contents="# TDD")
        fs.create_file(
            REPO_ROOT / "my-skills" / "review" / "SKILL.md", contents="# Review"
        )
        monkeypatch.chdir(REPO_ROOT)

        assert_invoke("source", "init")

        source_cfg = SourceConfig.load(REPO_ROOT / ".repo-skills" / "source.json")
        assert source_cfg.skills_dir == "my-skills"

    def test_detects_skills_with_categories(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        fs.create_file(
            REPO_ROOT / "skills" / "dev" / "tdd" / "SKILL.md", contents="# TDD"
        )
        fs.create_file(
            REPO_ROOT / "skills" / "ops" / "deploy" / "SKILL.md", contents="# Deploy"
        )
        monkeypatch.chdir(REPO_ROOT)

        assert_invoke("source", "init")

        source_cfg = SourceConfig.load(REPO_ROOT / ".repo-skills" / "source.json")
        assert source_cfg.skills_dir == "skills"
