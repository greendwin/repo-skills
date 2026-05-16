from __future__ import annotations

from pathlib import Path

from click.testing import Result
from pyfakefs.fake_filesystem import FakeFilesystem
from typer.testing import CliRunner

from skill_cli.main import app

REPO_SKILLS_DIR = Path("/repo/skills")
INSTALL_DIR = Path("/home/user/.claude/skills")
MANIFEST_PATH = INSTALL_DIR / ".skill-install.json"


def assert_invoke(
    *args: str,
    exit_code: int = 0,
) -> Result:
    runner = CliRunner()
    result = runner.invoke(app, args)
    assert result.exit_code == exit_code, (
        f"Expected exit code {exit_code}, got {result.exit_code}.\n"
        f"Output: {result.output}\n"
        f"Exception: {result.exception}"
    )
    return result


def create_repo_skill(fs: FakeFilesystem, name: str) -> Path:
    skill_dir = REPO_SKILLS_DIR / name
    fs.create_file(skill_dir / "SKILL.md", contents=f"# {name}")
    return skill_dir


def create_installed_skill(fs: FakeFilesystem, name: str) -> Path:
    skill_dir = INSTALL_DIR / name
    fs.create_file(skill_dir / "SKILL.md", contents=f"# {name}")
    return skill_dir
