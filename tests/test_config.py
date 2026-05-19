from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    ProviderConfig,
    ProviderRegistry,
    SkillEntry,
    SkillManifest,
    SourceConfig,
    SourceEntry,
    SourceRegistry,
    compute_file_hashes,
    default_config_dir,
)

# -- default_config_dir --


class TestDefaultConfigDir:
    def test_returns_xdg_when_set(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        result = default_config_dir()
        assert result == Path("/custom/config/repo-skills")

    def test_falls_back_to_dot_config(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", "/home/testuser")
        result = default_config_dir()
        assert result == Path("/home/testuser/.config/repo-skills")


# -- SourceConfig --


class TestSourceConfig:
    def test_load_missing_file_returns_defaults(self, fs: FakeFilesystem) -> None:
        cfg = SourceConfig.load(Path("/nonexistent/source.json"))
        assert cfg.name == ""
        assert cfg.skills_dir == "skills"

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
        path = Path("/repo/.repo-skills/source.json")
        cfg = SourceConfig(name="my-repo", skills_dir="custom/skills")
        cfg.save(path)

        loaded = SourceConfig.load(path)
        assert loaded.name == "my-repo"
        assert loaded.skills_dir == "custom/skills"

    def test_save_creates_parent_dirs(self, fs: FakeFilesystem) -> None:
        path = Path("/deep/nested/dir/source.json")
        cfg = SourceConfig(name="test")
        cfg.save(path)
        assert path.exists()


# -- ProviderConfig / ProviderRegistry --


class TestProviderRegistry:
    def test_load_missing_file_returns_empty(self, fs: FakeFilesystem) -> None:
        reg = ProviderRegistry.load(Path("/nonexistent/providers.json"))
        assert reg.providers == {}

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
        path = Path("/config/providers.json")
        reg = ProviderRegistry(
            providers={
                "claude": ProviderConfig(
                    name="claude", install_dir="/home/u/.claude/skills"
                ),
                "cursor": ProviderConfig(
                    name="cursor", install_dir="/home/u/.cursor/skills"
                ),
            }
        )
        reg.save(path)

        loaded = ProviderRegistry.load(path)
        assert len(loaded.providers) == 2
        assert loaded.providers["cursor"].install_dir == "/home/u/.cursor/skills"

    def test_load_existing_with_providers_keeps_them(self, fs: FakeFilesystem) -> None:
        path = Path("/config/providers.json")
        data = {
            "providers": {"custom": {"name": "custom", "install_dir": "/custom/path"}}
        }
        fs.create_file(path, contents=json.dumps(data))

        reg = ProviderRegistry.load(path)
        assert "custom" in reg.providers
        assert reg.providers["custom"].install_dir == "/custom/path"


# -- SourceRegistry --


class TestSourceRegistry:
    def test_load_missing_file_returns_empty(self, fs: FakeFilesystem) -> None:
        reg = SourceRegistry.load(Path("/nonexistent/sources.json"))
        assert reg.sources == {}

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
        path = Path("/config/sources.json")
        reg = SourceRegistry(
            sources={
                "my-repo": SourceEntry(path="/home/user/projects/my-repo"),
                "other": SourceEntry(path="/opt/other"),
            }
        )
        reg.save(path)

        loaded = SourceRegistry.load(path)
        assert len(loaded.sources) == 2
        assert loaded.sources["my-repo"].path == "/home/user/projects/my-repo"
        assert loaded.sources["other"].path == "/opt/other"


# -- SkillEntry / SkillManifest --


class TestSkillManifest:
    def test_load_missing_file_returns_empty(self, fs: FakeFilesystem) -> None:
        m = SkillManifest.load(Path("/nonexistent/manifest.json"))
        assert m.skills == {}

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
        path = Path("/config/manifest.json")
        m = SkillManifest(
            skills={
                "tdd": SkillEntry(
                    source="my-repo",
                    commit="abc1234",
                    files={"SKILL.md": "sha256:deadbeef"},
                ),
            }
        )
        m.save(path)

        loaded = SkillManifest.load(path)
        assert "tdd" in loaded.skills
        entry = loaded.skills["tdd"]
        assert entry.source == "my-repo"
        assert entry.commit == "abc1234"
        assert entry.files == {"SKILL.md": "sha256:deadbeef"}

    def test_skill_entry_defaults(self) -> None:
        entry = SkillEntry()
        assert entry.source == ""
        assert entry.commit is None
        assert entry.files == {}

    def test_multiple_skills(self, fs: FakeFilesystem) -> None:
        path = Path("/config/manifest.json")
        m = SkillManifest(
            skills={
                "tdd": SkillEntry(source="repo-a", commit="aaa"),
                "review": SkillEntry(source="repo-b", commit="bbb"),
            }
        )
        m.save(path)

        loaded = SkillManifest.load(path)
        assert set(loaded.skills.keys()) == {"tdd", "review"}


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
