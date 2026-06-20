from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated, Optional

import typer
from typer_di import Depends, TyperDI

from repo_skills.config import (
    REPO_SKILLS_DIR,
    ConfigState,
    SourceBrokenError,
    SourceConfig,
    load_skill_manifest,
    load_source_registry,
    load_source_state,
    save_skill_manifest,
    save_source_config,
    save_source_registry,
)
from repo_skills.console import console, fmt_data, fmt_ident, fmt_path
from repo_skills.discovery import DetectKind, detect_skills_dir, resolve_skills_dir
from repo_skills.errors import AppError, NoopError
from repo_skills.git import GitRepo
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


_INIT_HELP = (
    "Set up a skill source in the current repo (first-time setup); "
    "creates the source if absent or edits it if present."
)
_CONFIG_HELP = (
    "Edit this repo's skill source settings; "
    "creates the source if absent or edits it if present."
)


@dataclass(frozen=True)
class _RequestedChanges:
    name: str | None = None
    branch: str | None = None
    skills_dir: str | None = None


def _resolve_requested_changes(
    name: Annotated[
        Optional[str],
        typer.Option("--name", help="Source name override."),
    ] = None,
    branch: Annotated[
        Optional[str],
        typer.Option("--branch", help="Pin to this branch."),
    ] = None,
    skills_dir: Annotated[
        Optional[str],
        typer.Option(
            "--skills-dir", help="Skills root directory (must already exist)."
        ),
    ] = None,
) -> _RequestedChanges:
    return _RequestedChanges(name=name, branch=branch, skills_dir=skills_dir)


@app.command(name="init", help=_INIT_HELP)
def init(
    requested: _RequestedChanges = Depends(_resolve_requested_changes),
) -> None:
    _init_or_config_source(resolve_git_repo(Path.cwd()), requested)


@source_app.command(name="config", help=_CONFIG_HELP)
def source_config(
    requested: _RequestedChanges = Depends(_resolve_requested_changes),
) -> None:
    _init_or_config_source(resolve_git_repo(Path.cwd()), requested)


@source_app.command(name="init", hidden=True, help=_CONFIG_HELP)
def source_init(
    requested: _RequestedChanges = Depends(_resolve_requested_changes),
) -> None:
    _init_or_config_source(resolve_git_repo(Path.cwd()), requested)


def _init_or_config_source(git: GitRepo, requested: _RequestedChanges) -> None:
    if requested.branch is not None and not git.list_branches(requested.branch):
        raise AppError(
            f"Branch {fmt_ident(requested.branch)} not found.",
            props={"repo": fmt_path(git.root)},
        )

    if requested.skills_dir is not None:
        resolved = resolve_skills_dir(git.root, requested.skills_dir)
        if resolved is None:
            raise AppError(
                f"Skills dir {fmt_data(requested.skills_dir)} not found in repo.",
                props={"repo": fmt_path(git.root)},
            )
        requested = replace(requested, skills_dir=rel_posix(resolved, git.root))

    result = load_source_state(git.root)
    if result.state is ConfigState.OK:
        _handle_reinit(git.root, result.cfg, requested)
        return

    if result.state is ConfigState.BROKEN:
        # a config that exists on disk but won't load is broken, not fresh;
        # fresh-initialising would clobber the unparseable file (data loss)
        raise SourceBrokenError(git.root)

    _handle_fresh_init(git, requested)


def _handle_fresh_init(git: GitRepo, requested: _RequestedChanges) -> None:
    source_name = requested.name or git.root.name
    effective_branch = requested.branch or git.current_branch()

    if requested.skills_dir is not None:
        rel_skills = requested.skills_dir
    elif (detected := detect_skills_dir(git.root)).kind is DetectKind.SINGLE and (
        detected.path is not None
    ):
        # SINGLE always carries a path; the None-check is type narrowing
        rel_skills = rel_posix(detected.path, git.root)
    else:
        rel_skills = DEFAULT_SKILLS_DIR
        write_text(git.root / rel_skills / GIT_KEEP_FILE, "")

    config = SourceConfig(
        name=source_name,
        skills_dirs=[rel_skills],
        branch=effective_branch,
    )
    save_source_config(config, git.root)

    gitignore = git.root / REPO_SKILLS_DIR / GIT_IGNORE_FILE
    write_text(gitignore, "*\n")

    registry = load_source_registry()
    registry.register_source(source_name, git.root)
    save_source_registry(registry)

    console.print(f"Initialized source {fmt_ident(source_name)}.")


def _handle_reinit(
    git_root: Path, config: SourceConfig, requested: _RequestedChanges
) -> None:
    old_name = config.name
    effective_name = requested.name if requested.name is not None else old_name
    is_rename = effective_name != old_name
    cfg_changed = False
    changes: list[str] = []

    if is_rename:
        _rename_installed_skills(old_name, effective_name)
        config.name = effective_name
        cfg_changed = True
        changes.append(f"  name: {fmt_data(old_name)} → {fmt_data(effective_name)}")

    if requested.branch is not None and requested.branch != config.branch:
        changes.append(
            f"  branch: {fmt_data(config.branch)} → {fmt_data(requested.branch)}"
        )
        config.branch = requested.branch
        cfg_changed = True

    active_dir = config.active_dir or ""
    if requested.skills_dir is not None and requested.skills_dir != active_dir:
        old_dir, new_dir = fmt_data(active_dir), fmt_data(requested.skills_dir)
        changes.append(f"  skills_dir: {old_dir} → {new_dir}")
        config.skills_dirs = [requested.skills_dir]
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
    if not was_registered:
        console.print(f"Registered source {source_label}.")
    elif changes:
        console.print(f"Updated source {source_label}.")
    else:
        console.print(f"Source {source_label} already initialized.")

    for change in changes:
        console.print(change)


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

        result = load_source_state(entry.repo_root)
        if result.state is ConfigState.OK:
            if result.cfg.branch:
                message += f"  [dim](branch: {result.cfg.branch})[/dim]"
        elif result.state is ConfigState.BROKEN:
            message += "  [red](broken)[/red]"
        else:
            message += "  [red](not-inited)[/red]"
        console.print(message)


@source_app.command(name="remove", help="Remove a source from registry.")
def source_remove(
    source_name: str = typer.Argument(help="Name of the source to remove."),
    force: bool = typer.Option(
        False, "--force", help="Remove even if skills are installed (unregisters them)."
    ),
) -> None:
    source_registry = load_source_registry()

    if source_name not in source_registry.sources:
        raise AppError(f"Source {fmt_ident(source_name)} not found.")

    # removal only needs the repo path; no need to load the source (broken or not)
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
