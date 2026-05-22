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
    load_source_config,
    load_source_registry,
    save_skill_manifest,
    save_source_registry,
)
from repo_skills.discovery import detect_skills_dir, find_git_root
from repo_skills.errors import AppError, NoopError

from ._app import app
from ._deps import resolve_git_repo
from ._utils import echo

source_app = TyperDI(
    help="Manage skill sources.",
    no_args_is_help=True,
)
app.add_typer(source_app, name="source")


def _has_installed_skills(source_name: str) -> bool:
    manifest = load_skill_manifest()
    return any(e.source == source_name for e in manifest.skills.values())


def _rename_installed_skills(old_name: str, new_name: str) -> None:
    manifest = load_skill_manifest()
    changed = False
    for entry in manifest.skills.values():
        if entry.source == old_name:
            entry.source = new_name
            changed = True
    if changed:
        save_skill_manifest(manifest)


def _handle_reinit(
    git_root: Path,
    cfg: SourceConfig,
    name: str | None,
    *,
    branch: str | None,
) -> None:
    old_name = cfg.name
    old_branch = cfg.branch

    effective_name = name if name is not None else old_name
    is_rename = effective_name != old_name
    cfg_changed = False
    changes: list[str] = []

    if is_rename:
        _rename_installed_skills(old_name, effective_name)
        cfg.name = effective_name
        cfg_changed = True
        changes.append(
            f"  name: [green]{old_name}[/green] → [green]{effective_name}[/green]"
        )

    if branch is not None and branch != cfg.branch:
        changes.append(
            f"  branch: [green]{old_branch}[/green] → [green]{branch}[/green]"
        )
        cfg.branch = branch
        cfg_changed = True

    if cfg_changed:
        cfg.save(git_root / REPO_SKILLS_DIR / SOURCE_CONFIG_FILE)

    registry = load_source_registry()
    was_registered = effective_name in registry.sources or (
        is_rename and old_name in registry.sources
    )
    if is_rename:
        registry.sources.pop(old_name, None)
    registry.sources[effective_name] = SourceEntry(path=str(git_root))
    save_source_registry(registry)

    source_label = f"[green]{effective_name}[/green]"
    if changes:
        if was_registered:
            echo(f"Updated source {source_label}.")
        else:
            echo(f"Registered source {source_label}.")
        for change in changes:
            echo(change)
    elif not was_registered:
        echo(f"Registered source {source_label}.")
    else:
        echo(f"Source {source_label} already initialized.")


@app.command(name="init", hidden=True)
def init_redirect() -> None:
    raise AppError("Did you mean [blue]skills source init[/blue]?")


@source_app.command(name="init", help="Initialize a skill source in the current repo.")
def source_init(
    name: str | None = typer.Option(None, "--name", help="Source name override."),
    branch: str | None = typer.Option(None, "--branch", help="Pin to this branch."),
) -> None:
    cwd = Path.cwd()
    git_root = find_git_root(cwd)
    if git_root is None:
        raise AppError("Not inside a git repository.")

    repo_skills_dir = git_root / REPO_SKILLS_DIR
    source_json = repo_skills_dir / SOURCE_CONFIG_FILE

    git = resolve_git_repo(git_root)

    if branch is not None and not git.list_branches(branch):
        raise AppError(f"Branch [green]{branch}[/green] not found.")

    if source_json.exists():
        cfg = SourceConfig.load(source_json)
        _handle_reinit(git_root, cfg, name, branch=branch)
        return

    source_name = name or git_root.name
    effective_branch = branch or git.current_branch()

    skills_dir = detect_skills_dir(git_root)
    if skills_dir is not None:
        rel_skills = str(skills_dir.relative_to(git_root))
    else:
        rel_skills = "skills"
        gitkeep = git_root / rel_skills / ".gitkeep"
        gitkeep.parent.mkdir(parents=True, exist_ok=True)
        gitkeep.write_text("")

    cfg = SourceConfig(
        name=source_name,
        skills_dir=rel_skills,
        branch=effective_branch,
    )
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
        source_path = Path(entry.path)
        branch_suffix = ""
        if source_path.exists():
            cfg = load_source_config(source_path)
            if cfg.branch:
                branch_suffix = f"  [dim](branch: {cfg.branch})[/dim]"

        echo(
            f"  [white]{name:<{width}}[/white]"
            f"  [cyan]{entry.path}[/cyan]"
            f"{branch_suffix}"
        )


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
