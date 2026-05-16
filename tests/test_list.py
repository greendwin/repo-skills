from pathlib import Path

from click.testing import CliRunner
from pyfakefs.fake_filesystem import FakeFilesystem

from skill_cli.main import cli


def test_list_shows_repo_skills_as_not_installed(
    fs: FakeFilesystem,
) -> None:
    repo_skills = Path("/repo/skills")
    fs.create_dir(repo_skills / "grill-me")
    fs.create_file(repo_skills / "grill-me" / "SKILL.md")
    fs.create_dir(repo_skills / "tdd")
    fs.create_file(repo_skills / "tdd" / "SKILL.md")

    install_dir = Path("/home/user/.claude/skills")
    fs.create_dir(install_dir)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "list",
            "--repo-skills-dir",
            str(repo_skills),
            "--install-dir",
            str(install_dir),
        ],
    )
    assert result.exit_code == 0
    assert "grill-me" in result.output
    assert "tdd" in result.output
    assert "not installed" in result.output


def test_list_shows_installed_skills(
    fs: FakeFilesystem,
) -> None:
    repo_skills = Path("/repo/skills")
    fs.create_dir(repo_skills / "grill-me")
    fs.create_file(repo_skills / "grill-me" / "SKILL.md")

    install_dir = Path("/home/user/.claude/skills")
    fs.create_dir(install_dir / "grill-me")
    fs.create_file(install_dir / "grill-me" / "SKILL.md")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "list",
            "--repo-skills-dir",
            str(repo_skills),
            "--install-dir",
            str(install_dir),
        ],
    )
    assert result.exit_code == 0
    assert "grill-me" in result.output
    assert "installed" in result.output
    assert "not installed" not in result.output


def test_list_shows_orphan_skills(
    fs: FakeFilesystem,
) -> None:
    repo_skills = Path("/repo/skills")
    fs.create_dir(repo_skills)

    install_dir = Path("/home/user/.claude/skills")
    fs.create_dir(install_dir / "sentry")
    fs.create_file(install_dir / "sentry" / "SKILL.md")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "list",
            "--repo-skills-dir",
            str(repo_skills),
            "--install-dir",
            str(install_dir),
        ],
    )
    assert result.exit_code == 0
    assert "sentry" in result.output
    assert "orphan" in result.output


def test_list_ignores_dotfiles_in_install_dir(
    fs: FakeFilesystem,
) -> None:
    repo_skills = Path("/repo/skills")
    fs.create_dir(repo_skills / "tdd")

    install_dir = Path("/home/user/.claude/skills")
    fs.create_dir(install_dir)
    fs.create_file(install_dir / ".skill-install.json", contents="{}")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "list",
            "--repo-skills-dir",
            str(repo_skills),
            "--install-dir",
            str(install_dir),
        ],
    )
    assert result.exit_code == 0
    assert ".skill-install" not in result.output
