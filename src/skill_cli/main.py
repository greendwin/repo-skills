from pathlib import Path

import click

from skill_cli.discovery import find_install_dir, find_repo_skills_dir


@click.group()
def cli() -> None:
    """Manage Claude Code skills."""


@cli.command()
def install() -> None:
    """Install a skill from the repo."""


@cli.command()
def update() -> None:
    """Update installed skills from the repo."""


@cli.command()
def peek() -> None:
    """Show changes between repo and installed skills."""


@cli.command()
def merge() -> None:
    """Resolve conflicts between repo and installed skills."""


@cli.command(name="list")
@click.option("--repo-skills-dir", type=click.Path())
@click.option("--install-dir", type=click.Path())
def list_(
    repo_skills_dir: str | None,
    install_dir: str | None,
) -> None:
    """List available and installed skills."""
    repo_dir = Path(repo_skills_dir) if repo_skills_dir else find_repo_skills_dir()
    inst_dir = Path(install_dir) if install_dir else find_install_dir()

    if repo_dir is None:
        click.echo("Cannot find skills repo. Run from within the repo.", err=True)
        raise SystemExit(1)

    if inst_dir is None:
        click.echo("Cannot find install directory.", err=True)
        raise SystemExit(1)

    repo_skills = {d.name for d in repo_dir.iterdir() if d.is_dir()}
    installed = {
        d.name for d in inst_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    }

    all_names = sorted(repo_skills | installed)
    for name in all_names:
        in_repo = name in repo_skills
        in_installed = name in installed
        if in_repo and in_installed:
            status = "installed"
        elif in_repo:
            status = "not installed"
        else:
            status = "orphan"
        click.echo(f"  {name:30s} {status}")


@cli.command()
def uninstall() -> None:
    """Uninstall a skill."""
