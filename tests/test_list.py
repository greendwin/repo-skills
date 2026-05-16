from pyfakefs.fake_filesystem import FakeFilesystem

from tests.helper import (
    INSTALL_DIR,
    REPO_SKILLS_DIR,
    assert_invoke,
    create_installed_skill,
    create_repo_skill,
)


def test_list_shows_installed_skills_under_installed_header(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd", description="Test-driven development")
    create_installed_skill(fs, "tdd", description="Test-driven development")

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    lines = result.output.splitlines()
    assert "Installed" in lines[0]
    assert "tdd" in lines[1]
    assert "Test-driven development" in lines[1]


def test_list_shows_not_installed_skills_under_not_installed_header(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "grill-me", description="Stress-test a plan")
    fs.create_dir(INSTALL_DIR)

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    lines = result.output.splitlines()
    assert any("Not installed" in line for line in lines)
    assert any("grill-me" in line and "Stress-test a plan" in line for line in lines)


def test_list_shows_orphan_skills_under_not_in_repo_header(
    fs: FakeFilesystem,
) -> None:
    fs.create_dir(REPO_SKILLS_DIR)
    create_installed_skill(fs, "sentry", description="Access Sentry issues")

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    lines = result.output.splitlines()
    assert any("Not in repo" in line for line in lines)
    assert any("sentry" in line and "Access Sentry issues" in line for line in lines)


def test_list_hides_empty_sections(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd", description="TDD workflow")
    create_installed_skill(fs, "tdd", description="TDD workflow")

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    assert "Not installed" not in result.output
    assert "Not in repo" not in result.output


def test_list_shows_name_only_when_no_description(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "bare-skill")
    create_installed_skill(fs, "bare-skill")

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    assert "bare-skill" in result.output
    assert "—" not in result.output


def test_list_section_order_is_installed_then_not_in_repo_then_not_installed(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "available", description="Available skill")
    create_repo_skill(fs, "active", description="Active skill")
    create_installed_skill(fs, "active", description="Active skill")
    create_installed_skill(fs, "orphan", description="Orphan skill")

    result = assert_invoke(
        "list",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
    )
    output = result.output
    pos_installed = output.index("Installed")
    pos_not_in_repo = output.index("Not in repo")
    pos_not_installed = output.index("Not installed")
    assert pos_installed < pos_not_in_repo < pos_not_installed


def test_list_ignores_dotfiles_in_install_dir(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd", description="TDD")
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
