from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceConfig,
    SourceRegistry,
    compute_file_hashes,
    default_config_path,
    load_provider_registry,
    load_skill_manifest,
    load_source_config,
    load_source_registry,
    save_provider_registry,
    save_skill_manifest,
    save_source_config,
    save_source_registry,
)
from repo_skills.errors import AppError
from tests.cli.helper import FakeGitRepo

# -- Source.get_branch --


class TestGetBranch:
    def test_returns_config_branch_when_set(self) -> None:
        source = Source(
            repo_root=Path("/repo"),
            config=SourceConfig(name="", skills_dir="skills", branch="develop"),
            skills={},
        )
        git = FakeGitRepo(main_branch="main")
        assert source.get_branch(git) == "develop"

    def test_falls_back_to_main_when_empty(self) -> None:
        source = Source(
            repo_root=Path("/repo"),
            config=SourceConfig(name="", skills_dir="skills"),
            skills={},
        )
        git = FakeGitRepo(main_branch="trunk")
        assert source.get_branch(git) == "trunk"


# -- default_config_dir --


class TestDefaultConfigDir:
    def test_returns_xdg_when_set(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        result = default_config_path()
        assert result == Path("/custom/config/repo-skills")

    def test_falls_back_to_dot_config(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", "/home/testuser")
        result = default_config_path()
        assert result == Path("/home/testuser/.config/repo-skills")


# -- SourceConfig --


class TestSourceConfig:
    def test_load_missing_returns_none(self, fs: FakeFilesystem) -> None:
        cfg = load_source_config(Path("/nonexistent"))
        assert cfg is None

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
        repo_root = Path("/repo")
        cfg = SourceConfig(name="my-repo", skills_dir="custom/skills", branch="develop")
        save_source_config(cfg, repo_root)

        loaded = load_source_config(repo_root)
        assert loaded is not None
        assert loaded.name == "my-repo"
        assert loaded.skills_dir == "custom/skills"
        assert loaded.branch == "develop"

    def test_load_legacy_without_branch_defaults_to_empty(
        self, fs: FakeFilesystem
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(path, contents='{"name": "old-repo", "skills_dir": "skills"}')
        cfg = load_source_config(Path("/repo"))
        assert cfg is not None
        assert cfg.branch == ""

    def test_save_creates_parent_dirs(self, fs: FakeFilesystem) -> None:
        repo_root = Path("/deep/nested/dir")
        cfg = SourceConfig(name="test", skills_dir="skills")
        save_source_config(cfg, repo_root)
        assert (repo_root / ".repo-skills" / "source.json").exists()


# -- Provider / ProviderRegistry --


class TestProviderRegistry:
    def test_load_missing_file_creates_with_default_provider(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = load_provider_registry()
        assert "claude" in reg.providers
        assert reg.providers["claude"].install_path == Path("/home/user/.claude/skills")

    def test_load_existing_v1_does_not_reinject_defaults(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = load_provider_registry()
        reg.unregister_provider("claude")
        save_provider_registry(reg)

        reloaded = load_provider_registry()
        assert "claude" not in reloaded.providers

    def test_install_path_resolves_tilde(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = ProviderRegistry()
        reg.register_provider("test", "~/my-skills")
        assert reg.providers["test"].install_path == Path("/home/user/my-skills")

    def test_save_and_load_round_trip(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = load_provider_registry()
        reg.register_provider("cursor", "/opt/cursor/skills")
        save_provider_registry(reg)

        reloaded = load_provider_registry()
        assert len(reloaded.providers) == 2
        assert reloaded.providers["claude"].install_path == Path(
            "/home/user/.claude/skills"
        )
        assert reloaded.providers["cursor"].install_path == Path("/opt/cursor/skills")

    def test_require_unknown_raises(self) -> None:
        reg = ProviderRegistry()
        with pytest.raises(AppError):
            reg.require("nonexistent")

    def test_require_returns_registered_provider(self) -> None:
        reg = ProviderRegistry()
        reg.register_provider("test", "/opt/test")
        provider = reg.require("test")
        assert provider.name == "test"
        assert provider.install_path == Path("/opt/test")

    def test_unregister_removes_provider(self) -> None:
        reg = ProviderRegistry()
        reg.register_provider("test", "/opt/test")
        reg.unregister_provider("test")
        assert "test" not in reg.providers

    def test_unregister_missing_is_noop(self) -> None:
        reg = ProviderRegistry()
        reg.unregister_provider("nonexistent")

    def test_load_unversioned_file_migrates_and_injects_defaults(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        path = default_config_path("providers.json")
        data = {"providers": {"custom": {"install_dir": "/custom/path"}}}
        fs.create_file(path, contents=json.dumps(data))

        reg = load_provider_registry()
        assert "custom" in reg.providers
        assert "claude" in reg.providers


# -- SourceRegistry --


class TestSourceRegistry:
    def test_empty_registry_has_no_sources(self, fs: FakeFilesystem) -> None:
        reg = SourceRegistry()
        assert reg.sources == {}

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
        reg = SourceRegistry()
        reg.register_source("my-repo", Path("/home/user/projects/my-repo"))
        reg.register_source("other", Path("/opt/other"))
        save_source_registry(reg)

        loaded = load_source_registry()
        assert len(loaded.sources) == 2
        assert loaded.sources["my-repo"].repo_root == Path(
            "/home/user/projects/my-repo"
        )
        assert loaded.sources["other"].repo_root == Path("/opt/other")


# -- SkillManifest --


class TestSkillManifest:
    def test_load_missing_file_returns_empty(self, fs: FakeFilesystem) -> None:
        manifest = load_skill_manifest()
        assert dict(manifest.skills) == {}

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
        manifest = SkillManifest()
        manifest.register_skill(
            "tdd",
            source="my-repo",
            commit="abc1234",
            files={"SKILL.md": "sha256:deadbeef"},
        )
        save_skill_manifest(manifest)

        loaded = load_skill_manifest()
        assert "tdd" in loaded.skills
        entry = loaded.skills["tdd"]
        assert entry.source == "my-repo"
        assert entry.commit == "abc1234"
        assert entry.files == {"SKILL.md": "sha256:deadbeef"}

    def test_register_skill(self) -> None:
        manifest = SkillManifest()
        manifest.register_skill("tdd", source="my-repo", commit="abc")
        assert "tdd" in manifest.skills
        assert manifest.skills["tdd"].source == "my-repo"
        assert manifest.skills["tdd"].commit == "abc"

    def test_unregister_skill(self) -> None:
        manifest = SkillManifest()
        manifest.register_skill("tdd", source="my-repo")
        manifest.unregister_skill("tdd")
        assert "tdd" not in manifest.skills

    def test_skills_property_returns_mapping(self) -> None:
        from collections.abc import Mapping

        manifest = SkillManifest()
        manifest.register_skill("tdd", source="my-repo")
        assert isinstance(manifest.skills, Mapping)


# -- compute_file_hashes --


class TestComputeFileHashes:
    def test_single_file(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/tdd")
        fs.create_file(skill_dir / "SKILL.md", contents="# TDD skill")

        hashes = compute_file_hashes(skill_dir)
        assert len(hashes) == 1
        assert "SKILL.md" in hashes

        expected = "sha256:" + hashlib.sha256(b"# TDD skill").hexdigest()
        assert hashes["SKILL.md"] == expected

    def test_multiple_files(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/tdd")
        fs.create_file(skill_dir / "SKILL.md", contents="# TDD")
        fs.create_file(skill_dir / "tests.md", contents="# Tests")

        hashes = compute_file_hashes(skill_dir)
        assert len(hashes) == 2
        assert "SKILL.md" in hashes
        assert "tests.md" in hashes

    def test_nested_files(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/tdd")
        fs.create_file(skill_dir / "SKILL.md", contents="top")
        fs.create_file(skill_dir / "sub" / "deep.md", contents="nested")

        hashes = compute_file_hashes(skill_dir)
        assert len(hashes) == 2
        assert "SKILL.md" in hashes
        assert "sub/deep.md" in hashes

    def test_empty_directory(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/empty")
        fs.create_dir(skill_dir)

        hashes = compute_file_hashes(skill_dir)
        assert hashes == {}

    def test_hash_format(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/tdd")
        fs.create_file(skill_dir / "SKILL.md", contents="content")

        hashes = compute_file_hashes(skill_dir)
        value = hashes["SKILL.md"]
        assert value.startswith("sha256:")
        hex_part = value.split(":")[1]
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)
