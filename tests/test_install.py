from pyfakefs.fake_filesystem import FakeFilesystem

from skill_cli.manifest import Manifest
from tests.helper import (
    INSTALL_DIR,
    MANIFEST_PATH,
    REPO_SKILLS_DIR,
    assert_invoke,
    create_repo_skill,
)


def test_install_copies_skill_to_install_dir(
    fs: FakeFilesystem,
) -> None:
    skill_dir = create_repo_skill(fs, "tdd")
    fs.create_file(skill_dir / "tests.python.md", contents="# Python tests")
    fs.create_dir(INSTALL_DIR)

    assert_invoke(
        "install",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--commit",
        "abc1234",
    )

    with open(str(INSTALL_DIR / "tdd" / "SKILL.md")) as f:
        assert f.read() == "# tdd"
    with open(str(INSTALL_DIR / "tdd" / "tests.python.md")) as f:
        assert f.read() == "# Python tests"


def test_install_writes_manifest_entry(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_dir(INSTALL_DIR)

    assert_invoke(
        "install",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--commit",
        "abc1234",
    )

    manifest = Manifest.load(MANIFEST_PATH)
    assert manifest.repo_path == "/repo"
    assert "tdd" in manifest.skills
    assert manifest.skills["tdd"].commit == "abc1234"


def test_install_fails_if_skill_not_in_repo(
    fs: FakeFilesystem,
) -> None:
    fs.create_dir(REPO_SKILLS_DIR)
    fs.create_dir(INSTALL_DIR)

    result = assert_invoke(
        "install",
        "nope",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        exit_code=1,
    )
    assert "not found" in result.output


def test_install_fails_if_already_installed(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_dir(INSTALL_DIR / "tdd")

    result = assert_invoke(
        "install",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        exit_code=1,
    )
    assert "already installed" in result.output
