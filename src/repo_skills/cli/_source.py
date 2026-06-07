from __future__ import annotations

from pathlib import Path

import typer
from typer_di import TyperDI

from repo_skills.config import (
    REPO_SKILLS_DIR,
    SourceBrokenError,
    SourceConfig,
    load_skill_manifest,
    load_source_config,
    load_source_registry,
    save_skill_manifest,
    save_source_config,
    save_source_registry,
)
from repo_skills.console import console, fmt_data, fmt_ident, fmt_path
from repo_skills.discovery import detect_skills_dir
from repo_skills.errors import AppError, NoopError
from repo_skills.utils import rel_posix, write_text

from ._app import app
from ._deps import resolve_git_repo

DEFAULT_SKILLS_DIR = "skills"
GIT_KEEP_FILE = ".gitkeep"
GIT_IGNORE_FILE = ".gitignore"


source_app = TyperDI(
    help="Manage skill sources.",
    no_args_is_help=True,
)
app.add_typer(source_app, name="source")


@app.command(name="init", hidden=True)
def init_redirect() -> None:
    raise AppError("Did you mean [blue]skills source init[/blue]?")


@source_app.command(name="init", help="Initialize a skill source in the current repo.")
def source_init(
    name: str | None = typer.Option(None, "--name", help="Source name override."),
    branch: str | None = typer.Option(None, "--branch", help="Pin to this branch."),
) -> None:
    git = resolve_git_repo(Path.cwd())

    if branch is not None and not git.list_branches(branch):
        raise AppError(f"Branch {fmt_ident(branch)} not found.")

    cfg = load_source_config(git.root)
    if cfg is not None:
        _handle_reinit(git.root, cfg, name=name, branch=branch)
        return

    source_name = name or git.root.name
    effective_branch = branch or git.current_branch()

    skills_dir = detect_skills_dir(git.root)
    if skills_dir is not None:
        rel_skills = rel_posix(skills_dir, git.root)
    else:
        rel_skills = DEFAULT_SKILLS_DIR
        write_text(git.root / rel_skills / GIT_KEEP_FILE, "")

    config = SourceConfig(
        name=source_name,
        skills_dir=rel_skills,
        branch=effective_branch,
    )
    save_source_config(config, git.root)

    gitignore = git.root / REPO_SKILLS_DIR / GIT_IGNORE_FILE
    gitignore.write_text("*\n")

    registry = load_source_registry()
    registry.register_source(source_name, git.root)
    save_source_registry(registry)

    console.print(f"Initialized source {fmt_ident(source_name)}.")


def _handle_reinit(
    git_root: Path, config: SourceConfig, *, name: str | None, branch: str | None
) -> None:
    old_name = config.name
    old_branch = config.branch

    effective_name = name if name is not None else old_name
    is_rename = effective_name != old_name
    cfg_changed = False
    changes: list[str] = []

    if is_rename:
        _rename_installed_skills(old_name, effective_name)
        config.name = effective_name
        cfg_changed = True
        changes.append(f"  name: {fmt_data(old_name)} → {fmt_data(effective_name)}")

    if branch is not None and branch != config.branch:
        changes.append(f"  branch: {fmt_data(old_branch)} → {fmt_data(branch)}")
        config.branch = branch
        cfg_changed = True

    if cfg_changed:
        save_source_config(config, git_root)

    registry = load_source_registry()
    was_registered = effective_name in registry.sources or (
        is_rename and old_name in registry.sources
    )
    if is_rename:
        registry.unregister_source(old_name)
    registry.register_source(effective_name, git_root)
    save_source_registry(registry)

    source_label = fmt_ident(effective_name)
    if changes:
        if was_registered:
            console.print(f"Updated source {source_label}.")
        else:
            console.print(f"Registered source {source_label}.")
        for change in changes:
            console.print(change)
    elif not was_registered:
        console.print(f"Registered source {source_label}.")
    else:
        console.print(f"Source {source_label} already initialized.")


def _rename_installed_skills(old_name: str, new_name: str) -> None:
    manifest = load_skill_manifest()
    to_update = [
        (name, entry)
        for name, entry in manifest.skills.items()
        if entry.source == old_name
    ]
    for name, entry in to_update:
        manifest.register_skill(
            name,
            source_name=new_name,
            baseline=entry.baseline,
            detached=entry.detached,
        )
    if to_update:
        save_skill_manifest(manifest)


@source_app.command(name="list", help="List all registered sources.")
def source_list() -> None:
    registry = load_source_registry()

    if not registry.sources:
        raise NoopError("[dim]No sources registered.[/dim]")

    console.print("[yellow]Skill sources[/yellow]")
    width = max(len(n) for n in registry.sources)
    width = max(width, 16)
    for name, entry in registry.sources.items():
        message = f"  [white]{name:<{width}}[/white]  [cyan]{entry.repo_root}[/cyan]"

        if not entry.repo_root.exists():
            message += "  [red](missing)[/red]"
            console.print(message)
            continue

        config = load_source_config(entry.repo_root)
        if config is None:
            message += "  [red](not-inited)[/red]"
        elif config.branch:
            message += f"  [dim](branch: {config.branch})[/dim]"
        console.print(message)


@source_app.command(name="remove", help="Remove a source from registry.")
def source_remove(
    source_name: str = typer.Argument(help="Name of the source to remove."),
    force: bool = typer.Option(
        False, "--force", help="Remove even if skills are installed (unregisters them)."
    ),
) -> None:
    source_registry = load_source_registry()

    try:
        repo_root = source_registry.get_source(source_name, load_skills=False).repo_root
    except SourceBrokenError:
        # silently ignore broken sources, just remove them from the registry
        repo_root = source_registry.sources[source_name].repo_root

    manifest = load_skill_manifest()
    matching = [
        skill_name
        for skill_name, entry in manifest.skills.items()
        if entry.source == source_name
    ]

    if matching:
        if not force:
            raise AppError("Cannot remove a source with installed skills.")

        for skill_name in matching:
            manifest.unregister_skill(skill_name)
        save_skill_manifest(manifest)

        names = ", ".join(fmt_ident(n) for n in sorted(matching))
        console.print(f"Unregistered {fmt_data(len(matching))} skill(s): {names}.")

    source_registry.unregister_source(source_name)
    save_source_registry(source_registry)

    console.print(f"Removed source {fmt_ident(source_name)} at {fmt_path(repo_root)}.")
