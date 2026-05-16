import os
import shutil
from pathlib import Path

import click

from skill_cli.discovery import find_install_dir, find_repo_skills_dir
from skill_cli.manifest import Manifest, SkillEntry, default_manifest_path


def _copytree(src: Path, dst: Path) -> None:
    os.makedirs(str(dst), exist_ok=True)
    for item in os.listdir(str(src)):
        s = os.path.join(str(src), item)
        d = os.path.join(str(dst), item)
        if os.path.isdir(s):
            _copytree(Path(s), Path(d))
        else:
            with open(s, "rb") as f_in, open(d, "wb") as f_out:
                f_out.write(f_in.read())


@click.group()
def cli() -> None:
    """Manage Claude Code skills."""


@cli.command()
@click.argument("name")
@click.option("--repo-skills-dir", type=click.Path())
@click.option("--install-dir", type=click.Path())
@click.option("--manifest-path", type=click.Path())
@click.option("--commit", type=str, default=None)
def install(
    name: str,
    repo_skills_dir: str | None,
    install_dir: str | None,
    manifest_path: str | None,
    commit: str | None,
) -> None:
    """Install a skill from the repo."""

    repo_dir = Path(repo_skills_dir) if repo_skills_dir else find_repo_skills_dir()
    inst_dir = Path(install_dir) if install_dir else find_install_dir()
    mpath = Path(manifest_path) if manifest_path else default_manifest_path()

    if repo_dir is None:
        click.echo("Cannot find skills repo. Run from within the repo.", err=True)
        raise SystemExit(1)

    src = repo_dir / name
    if not src.is_dir():
        click.echo(f"Skill '{name}' not found in repo.", err=True)
        raise SystemExit(1)

    if inst_dir is None:
        inst_dir = Path(mpath).parent
    os.makedirs(str(inst_dir), exist_ok=True)

    dst = inst_dir / name
    if dst.exists():
        click.echo(f"Skill '{name}' is already installed.", err=True)
        raise SystemExit(1)

    _copytree(src, dst)

    manifest = Manifest.load(mpath)
    manifest.repo_path = str(repo_dir.parent)
    manifest.skills[name] = SkillEntry(commit=commit or "")
    manifest.save(mpath)

    click.echo(f"Installed '{name}'.")


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
@click.argument("name")
@click.option("--install-dir", type=click.Path())
@click.option("--manifest-path", type=click.Path())
def uninstall(
    name: str,
    install_dir: str | None,
    manifest_path: str | None,
) -> None:
    """Uninstall a skill."""

    mpath = Path(manifest_path) if manifest_path else default_manifest_path()
    inst_dir = Path(install_dir) if install_dir else find_install_dir()

    if inst_dir is None:
        click.echo("Cannot find install directory.", err=True)
        raise SystemExit(1)

    dst = inst_dir / name
    if not dst.exists():
        click.echo(f"Skill '{name}' is not installed.", err=True)
        raise SystemExit(1)

    shutil.rmtree(str(dst))

    manifest = Manifest.load(mpath)
    manifest.skills.pop(name, None)
    manifest.save(mpath)

    click.echo(f"Uninstalled '{name}'.")
