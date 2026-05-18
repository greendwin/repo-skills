from collections.abc import Generator

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.manifest import Manifest
from tests.cli.helper import (
    INSTALL_DIR,
    MANIFEST_PATH,
    REPO_SKILLS_DIR,
    FakeGitRepo,
    assert_invoke,
    create_repo_skill,
    install_fake_git,
    uninstall_fake_git,
)


@pytest.fixture(autouse=True)
def _fake_git() -> Generator[FakeGitRepo]:
    fake = FakeGitRepo(commits={"tdd": "abc1234", "nope": "abc1234"})
    install_fake_git(fake)
    yield fake
    uninstall_fake_git()


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
        "--offline",
    )

    with open(INSTALL_DIR / "tdd" / "SKILL.md") as f:
        assert f.read() == "# tdd"
    with open(INSTALL_DIR / "tdd" / "tests.python.md") as f:
        assert f.read() == "# Python tests"


def test_install_writes_manifest_with_auto_detected_commit(
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
        "--offline",
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
        "--offline",
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
        "--offline",
        exit_code=1,
    )
    assert "already installed" in result.output


def test_install_fails_if_not_on_main_branch(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
) -> None:
    _fake_git.branch = "feature/xyz"
    create_repo_skill(fs, "tdd")
    fs.create_dir(INSTALL_DIR)

    result = assert_invoke(
        "install",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
        exit_code=1,
    )
    assert "Not on main branch" in result.output


def test_install_fails_if_repo_is_dirty(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
) -> None:
    _fake_git.clean = False
    create_repo_skill(fs, "tdd")
    fs.create_dir(INSTALL_DIR)

    result = assert_invoke(
        "install",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
        exit_code=1,
    )
    assert "uncommitted changes" in result.output


def test_install_fails_if_commit_content_mismatch(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
) -> None:
    _fake_git.verified["tdd"] = False
    create_repo_skill(fs, "tdd")
    fs.create_dir(INSTALL_DIR)

    result = assert_invoke(
        "install",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
        exit_code=1,
    )
    assert "does not match commit" in result.output


def test_install_pulls_by_default(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
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
    )

    assert _fake_git.pulled is True


def test_install_skips_pull_when_offline(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
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
        "--offline",
    )

    assert _fake_git.pulled is False
