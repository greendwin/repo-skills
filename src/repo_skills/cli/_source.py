from __future__ import annotations

from pathlib import Path

import typer
from typer_di import TyperDI

from repo_skills._config import (
    SkillManifest,
    SourceConfig,
    SourceEntry,
    SourceRegistry,
    default_config_dir,
)
from repo_skills._discovery import detect_skills_dir, find_git_root
from repo_skills.errors import AppError

from ._app import app
from ._utils import echo

source_app = TyperDI(
    help="Manage skill sources.",
    no_args_is_help=True,
)
app.add_typer(source_app, name="source")


def _has_installed_skills(source_name: str) -> bool:
    manifest_path = default_config_dir() / "skill-manifest.json"
    manifest = SkillManifest.load(manifest_path)
    return any(e.source == source_name for e in manifest.skills.values())


def _handle_reinit(
    cfg: SourceConfig,
    name: str | None,
    git_root: Path,
) -> None:
    old_name = cfg.name

    if name is None or name == old_name:
        echo(f"Source [green]{old_name}[/green] already initialized.")
        return

    if _has_installed_skills(old_name):
        raise AppError("Renaming installed skills is not yet supported.")

    cfg.name = name
    cfg.save(git_root / ".repo-skills" / "source.json")

    registry_path = default_config_dir() / "sources.json"
    registry = SourceRegistry.load(registry_path)
    registry.sources.pop(old_name, None)
    registry.sources[name] = SourceEntry(path=str(git_root))
    registry.save(registry_path)

    echo(f"Renamed source [cyan]{old_name}[/cyan] to [green]{name}[/green].")


@source_app.command(name="init", help="Initialize a skill source in the current repo.")
def source_init(
    name: str | None = typer.Option(None, "--name", help="Source name override."),
) -> None:
    cwd = Path.cwd()
    git_root = find_git_root(cwd)
    if git_root is None:
        raise AppError("Not inside a git repository.")

    repo_skills_dir = git_root / ".repo-skills"
    source_json = repo_skills_dir / "source.json"

    if source_json.exists():
        cfg = SourceConfig.load(source_json)
        _handle_reinit(cfg, name, git_root)
        return

    source_name = name or git_root.name

    skills_dir = detect_skills_dir(git_root)
    if skills_dir is not None:
        rel_skills = str(skills_dir.relative_to(git_root))
    else:
        rel_skills = "skills"
        gitkeep = git_root / rel_skills / ".gitkeep"
        gitkeep.parent.mkdir(parents=True, exist_ok=True)
        gitkeep.write_text("")

    cfg = SourceConfig(name=source_name, skills_dir=rel_skills)
    cfg.save(source_json)

    gitignore = repo_skills_dir / ".gitignore"
    gitignore.write_text("source.json\n")

    registry_path = default_config_dir() / "sources.json"
    registry = SourceRegistry.load(registry_path)
    registry.sources[source_name] = SourceEntry(path=str(git_root))
    registry.save(registry_path)

    echo(f"Initialized source [green]{source_name}[/green].")
