from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.manifest import Manifest, SkillEntry
from tests.cli.helper import (
    INSTALL_DIR,
    MANIFEST_PATH,
    assert_invoke,
    create_installed_skill,
)


def test_uninstall_removes_skill_directory(
    fs: FakeFilesystem,
) -> None:
    create_installed_skill(fs, "tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="abc1234")},
    )
    manifest.save(MANIFEST_PATH)

    assert_invoke(
        "uninstall",
        "tdd",
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
    )

    assert not (INSTALL_DIR / "tdd").exists()


def test_uninstall_removes_manifest_entry(
    fs: FakeFilesystem,
) -> None:
    create_installed_skill(fs, "tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={
            "tdd": SkillEntry(commit="abc1234"),
            "grill-me": SkillEntry(commit="abc1234"),
        },
    )
    manifest.save(MANIFEST_PATH)

    assert_invoke(
        "uninstall",
        "tdd",
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
    )

    manifest = Manifest.load(MANIFEST_PATH)
    assert "tdd" not in manifest.skills
    assert "grill-me" in manifest.skills


def test_uninstall_fails_if_not_installed(
    fs: FakeFilesystem,
) -> None:
    fs.create_dir(INSTALL_DIR)

    result = assert_invoke(
        "uninstall",
        "nope",
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        exit_code=1,
    )
    assert "not installed" in result.output
