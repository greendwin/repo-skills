from __future__ import annotations

from pathlib import Path

import typer
from typer_di import TyperDI

from repo_skills._config import (
    SourceConfig,
    SourceEntry,
    SourceRegistry,
    default_config_dir,
)
from repo_skills._discovery import detect_skills_dir, find_git_root

from ._app import app

source_app = TyperDI(
    help="Manage skill sources.",
    no_args_is_help=True,
)
app.add_typer(source_app, name="source")


@source_app.command(name="init", help="Initialize a skill source in the current repo.")
def source_init(
    name: str | None = typer.Option(None, "--name", help="Source name override."),
) -> None:
    cwd = Path.cwd()
    git_root = find_git_root(cwd)
    if git_root is None:
        typer.echo("Not inside a git repository.", err=True)
        raise typer.Exit(1)

    repo_skills_dir = git_root / ".repo-skills"
    source_json = repo_skills_dir / "source.json"

    if source_json.exists():
        typer.echo("Source already initialized.", err=True)
        raise typer.Exit(1)

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

    typer.echo(f"Initialized source '{source_name}'.")
