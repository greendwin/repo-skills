from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills._config import SourceConfig, SourceRegistry
from tests.helper import assert_invoke

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

        assert "Initialized source 'my-project'" in result.output

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

        assert "Initialized source 'custom-name'" in result.output


class TestSourceInitErrors:
    def test_already_initialized(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
        _make_git_repo(fs)
        fs.create_file(
            REPO_ROOT / ".repo-skills" / "source.json", contents='{"name":"x"}'
        )
        monkeypatch.chdir(REPO_ROOT)

        result = assert_invoke("source", "init", exit_code=1)
        assert "already initialized" in result.output.lower()

    def test_not_in_git_repo(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fs.create_dir("/not-a-repo")
        monkeypatch.chdir("/not-a-repo")

        result = assert_invoke("source", "init", exit_code=1)
        assert "git" in result.output.lower()


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
