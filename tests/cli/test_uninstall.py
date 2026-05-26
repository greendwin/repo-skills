from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config.deprecated import (
    ManifestSkill,
)
from tests.cli.helper import (
    INSTALL_DIR,
    assert_invoke,
    assert_words_in_message,
    create_installed_skill,
    load_manifest,
    register_provider,
    save_manifest,
)


def _entry(source: str = "my-project") -> ManifestSkill:
    return ManifestSkill(
        source=source, commit="abc1234", files={"SKILL.md": "sha256:aaa"}
    )


class TestUninstall:
    def test_removes_skill_directory(self, fs: FakeFilesystem) -> None:
        create_installed_skill(fs, "tdd")
        save_manifest({"tdd": _entry()})

        assert_invoke("uninstall", "tdd")

        assert not (INSTALL_DIR / "tdd").exists()

    def test_removes_manifest_entry(self, fs: FakeFilesystem) -> None:
        create_installed_skill(fs, "tdd")
        save_manifest({"tdd": _entry(), "grill-me": _entry()})

        assert_invoke("uninstall", "tdd")

        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert "grill-me" in manifest.skills

    def test_removes_from_all_providers(self, fs: FakeFilesystem) -> None:
        create_installed_skill(fs, "tdd")
        cursor_dir = Path("/home/user/.cursor/skills")
        fs.create_file(cursor_dir / "tdd" / "SKILL.md", contents="# tdd")

        register_provider("cursor", str(cursor_dir))

        save_manifest({"tdd": _entry()})

        assert_invoke("uninstall", "tdd")

        assert not (INSTALL_DIR / "tdd").exists()
        assert not (cursor_dir / "tdd").exists()

    def test_errors_when_not_in_manifest(self, fs: FakeFilesystem) -> None:
        save_manifest({})

        result = assert_invoke("uninstall", "nope", expect_error=True)

        assert_words_in_message(result.exception.message, "not installed")


class TestUninstallMultiple:
    def test_removes_multiple_skills(self, fs: FakeFilesystem) -> None:
        create_installed_skill(fs, "tdd")
        create_installed_skill(fs, "review")
        save_manifest({"tdd": _entry(), "review": _entry()})

        assert_invoke("uninstall", "tdd", "review")

        assert not (INSTALL_DIR / "tdd").exists()
        assert not (INSTALL_DIR / "review").exists()
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert "review" not in manifest.skills

    def test_fails_fast_on_missing_skill(self, fs: FakeFilesystem) -> None:
        create_installed_skill(fs, "tdd")
        save_manifest({"tdd": _entry()})

        result = assert_invoke("uninstall", "tdd", "missing", expect_error=True)

        assert_words_in_message(result.exception.message, "missing", "not installed")
        assert not (INSTALL_DIR / "tdd").exists()
