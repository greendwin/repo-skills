from pyfakefs.fake_filesystem import FakeFilesystem

from tests.helper import (
    INSTALL_DIR,
    REPO_SKILLS_DIR,
    assert_invoke,
    create_installed_skill,
    create_repo_skill,
)


def test_list_shows_repo_skills_as_not_installed(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "grill-me")
    create_repo_skill(fs, "tdd")
    fs.create_dir(INSTALL_DIR)

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    assert "grill-me" in result.output
    assert "tdd" in result.output
    assert "not installed" in result.output


def test_list_shows_installed_skills(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "grill-me")
    create_installed_skill(fs, "grill-me")

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    assert "grill-me" in result.output
    assert "installed" in result.output
    assert "not installed" not in result.output


def test_list_shows_orphan_skills(
    fs: FakeFilesystem,
) -> None:
    fs.create_dir(REPO_SKILLS_DIR)
    create_installed_skill(fs, "sentry")

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    assert "sentry" in result.output
    assert "orphan" in result.output


def test_list_ignores_dotfiles_in_install_dir(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_dir(INSTALL_DIR)
    fs.create_file(INSTALL_DIR / ".skill-install.json", contents="{}")

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    assert ".skill-install" not in result.output
