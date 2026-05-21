from __future__ import annotations

from pathlib import Path

import typer
from typer_di import TyperDI

from repo_skills.config import (
    REPO_SKILLS_DIR,
    SOURCE_CONFIG_FILE,
    SourceConfig,
    SourceEntry,
    load_skill_manifest,
    load_source_registry,
    save_source_registry,
)
from repo_skills.discovery import detect_skills_dir, find_git_root
from repo_skills.errors import AppError, NoopError

from ._app import app
from ._utils import echo

source_app = TyperDI(
    help="Manage skill sources.",
    no_args_is_help=True,
)
app.add_typer(source_app, name="source")


def _has_installed_skills(source_name: str) -> bool:
    manifest = load_skill_manifest()
    return any(e.source == source_name for e in manifest.skills.values())


def _handle_reinit(
    cfg: SourceConfig,
    name: str | None,
    git_root: Path,
) -> None:
    old_name = cfg.name

    effective_name = name if name is not None else old_name
    is_rename = effective_name != old_name

    if is_rename:
        if _has_installed_skills(old_name):
            raise AppError("Renaming installed skills is not yet supported.")

        cfg.name = effective_name
        cfg.save(git_root / REPO_SKILLS_DIR / SOURCE_CONFIG_FILE)

    registry = load_source_registry()
    was_registered = effective_name in registry.sources
    if is_rename:
        registry.sources.pop(old_name, None)
    registry.sources[effective_name] = SourceEntry(path=str(git_root))
    save_source_registry(registry)

    if is_rename:
        old = f"[green]{old_name}[/green]"
        new = f"[green]{effective_name}[/green]"
        echo(f"Renamed source {old} to {new}.")
    elif not was_registered:
        echo(f"Registered source [green]{old_name}[/green].")
    else:
        echo(f"Source [green]{old_name}[/green] already initialized.")


@source_app.command(name="init", help="Initialize a skill source in the current repo.")
def source_init(
    name: str | None = typer.Option(None, "--name", help="Source name override."),
) -> None:
    cwd = Path.cwd()
    git_root = find_git_root(cwd)
    if git_root is None:
        raise AppError("Not inside a git repository.")

    repo_skills_dir = git_root / REPO_SKILLS_DIR
    source_json = repo_skills_dir / SOURCE_CONFIG_FILE

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
    gitignore.write_text("*\n")

    registry = load_source_registry()
    registry.sources[source_name] = SourceEntry(path=str(git_root))
    save_source_registry(registry)

    echo(f"Initialized source [green]{source_name}[/green].")


@source_app.command(name="list", help="List all registered sources.")
def source_list() -> None:
    registry = load_source_registry()

    if not registry.sources:
        raise NoopError("[dim]No sources registered.[/dim]")

    echo("[yellow]Skill sources[/yellow]")
    width = max(len(n) for n in registry.sources)
    width = max(width, 16)
    for name, entry in registry.sources.items():
        echo(f"  [white]{name:<{width}}[/white]  [cyan]{entry.path}[/cyan]")


@source_app.command(name="remove", help="Remove a source from registry.")
def source_remove(
    name: str = typer.Argument(help="Name of the source to remove."),
) -> None:
    registry = load_source_registry()

    if name not in registry.sources:
        raise AppError(f"Source [green]{name}[/green] not found.")

    if _has_installed_skills(name):
        raise AppError("Cannot remove a source with installed skills.")

    source_path = registry.sources[name].path

    del registry.sources[name]
    save_source_registry(registry)

    echo(f"Removed source [green]{name}[/green] at [dim]{source_path}[/dim].")
