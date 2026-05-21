from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    ProviderConfig,
    ProviderRegistry,
    SkillEntry,
    SkillManifest,
)
from tests.cli.helper import (
    INSTALL_DIR,
    SOURCE_CONFIG_DIR,
    assert_invoke,
    assert_words_in_message,
    create_installed_skill,
)

MANIFEST_PATH = SOURCE_CONFIG_DIR / "skill-manifest.json"


@pytest.fixture()
def _env(fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/user")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")


def _save_manifest(skills: dict[str, SkillEntry]) -> None:
    manifest = SkillManifest(skills=skills)
    manifest.save(MANIFEST_PATH)


def _entry(source: str = "my-project") -> SkillEntry:
    return SkillEntry(source=source, commit="abc1234", files={"SKILL.md": "sha256:aaa"})


class TestUninstall:
    def test_removes_skill_directory(self, fs: FakeFilesystem, _env: None) -> None:
        create_installed_skill(fs, "tdd")
        _save_manifest({"tdd": _entry()})

        assert_invoke("uninstall", "tdd")

        assert not (INSTALL_DIR / "tdd").exists()

    def test_removes_manifest_entry(self, fs: FakeFilesystem, _env: None) -> None:
        create_installed_skill(fs, "tdd")
        _save_manifest({"tdd": _entry(), "grill-me": _entry()})

        assert_invoke("uninstall", "tdd")

        manifest = SkillManifest.load(MANIFEST_PATH)
        assert "tdd" not in manifest.skills
        assert "grill-me" in manifest.skills

    def test_removes_from_all_providers(self, fs: FakeFilesystem, _env: None) -> None:
        create_installed_skill(fs, "tdd")
        cursor_dir = Path("/home/user/.cursor/skills")
        fs.create_file(cursor_dir / "tdd" / "SKILL.md", contents="# tdd")

        ProviderRegistry(
            providers={
                "cursor": ProviderConfig(name="cursor", install_dir=str(cursor_dir))
            }
        ).save(SOURCE_CONFIG_DIR / "providers.json")

        _save_manifest({"tdd": _entry()})

        assert_invoke("uninstall", "tdd")

        assert not (INSTALL_DIR / "tdd").exists()
        assert not (cursor_dir / "tdd").exists()

    def test_errors_when_not_in_manifest(self, fs: FakeFilesystem, _env: None) -> None:
        _save_manifest({})

        result = assert_invoke("uninstall", "nope", expect_error=True)

        assert_words_in_message(result.exception.message, "not installed")
