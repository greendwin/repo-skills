from __future__ import annotations

from collections.abc import Sequence
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
    load_source_config,
    load_source_registry,
    save_skill_manifest,
    save_source_config,
    save_source_registry,
)
from repo_skills.console import console, fmt_data, fmt_ident, fmt_path
from repo_skills.discovery import (
    DetectKind,
    detect_skills_dir,
    has_any_skill,
    normalize_repo_dir,
)
from repo_skills.errors import AppError, NoopError
from repo_skills.git import GitRepo
from repo_skills.utils import rel_posix, write_text

from ._app import app
from ._deps import resolve_git_repo

_ChangeValue = str | list[str]

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
    skills_dirs: list[str] | None = None


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
        Optional[list[str]],
        typer.Option(
            "--skills-dir",
            help="Skills directory (repeatable); bypasses auto-detection.",
        ),
    ] = None,
) -> _RequestedChanges:
    skills_dirs = list(skills_dir) if skills_dir else None
    return _RequestedChanges(name=name, branch=branch, skills_dirs=skills_dirs)


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
        raise _repo_error(git, f"Branch {fmt_ident(requested.branch)} not found.")

    if requested.skills_dirs is not None:
        normalized = _normalize_skills_dirs(git, requested.skills_dirs)
        requested = replace(requested, skills_dirs=normalized)

    result = load_source_config(git.root)
    if result.state is ConfigState.OK:
        _handle_reinit(git.root, result.cfg, requested)
        return

    if result.state is ConfigState.BROKEN:
        # a config that exists on disk but won't load is broken, not fresh;
        # fresh-initialising would clobber the unparseable file (data loss)
        raise SourceBrokenError(git.root)

    _handle_fresh_init(git, requested)


def _normalize_skills_dirs(git: GitRepo, skills_dirs: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for skills_dir in skills_dirs:
        resolved = normalize_repo_dir(git.root, skills_dir)
        if resolved is None:
            raise _repo_error(
                git, f"Skills dir {fmt_data(skills_dir)} escapes the repo."
            )

        normalized.append(rel_posix(resolved, git.root))

    return list(dict.fromkeys(normalized))


def _repo_error(git: GitRepo, msg: str) -> AppError:
    return AppError(msg, props={"repo": fmt_path(git.root)})


def _note_empty_skills_dirs(repo_root: Path, skills_dirs: Sequence[str]) -> None:
    for rel in skills_dirs:
        if not _dir_has_skills(repo_root / rel):
            console.print(
                f"[dim]Note:[/dim] {fmt_path(rel)} "
                f"[dim]currently has no skills.[/dim]"
            )


def _dir_has_skills(path: Path) -> bool:
    return path.is_dir() and has_any_skill(path)


def _handle_fresh_init(git: GitRepo, requested: _RequestedChanges) -> None:
    source_name = requested.name or git.root.name
    effective_branch = requested.branch or git.current_branch()

    if requested.skills_dirs is not None:
        skills_dirs = requested.skills_dirs
        _note_empty_skills_dirs(git.root, skills_dirs)
    else:
        skills_dirs = [_detect_fresh_skills_dir(git)]

    config = SourceConfig(
        name=source_name,
        skills_dirs=skills_dirs,
        branch=effective_branch,
    )
    save_source_config(config, git.root)

    gitignore = git.root / REPO_SKILLS_DIR / GIT_IGNORE_FILE
    write_text(gitignore, "*\n")

    registry = load_source_registry()
    registry.register_source(source_name, git.root)
    save_source_registry(registry)

    console.print(f"Initialized source {fmt_ident(source_name)}.")


def _detect_fresh_skills_dir(git: GitRepo) -> str:
    detected = detect_skills_dir(git.root)
    if detected.kind is DetectKind.SINGLE:
        return rel_posix(detected.require_path(), git.root)

    if detected.kind is DetectKind.AMBIGUOUS:
        raise _repo_error(
            git,
            "Skills are spread across the repo root; cannot auto-detect a "
            "skills directory. Re-run with explicit "
            f"{fmt_data('--skills-dir')} values.",
        )

    write_text(git.root / DEFAULT_SKILLS_DIR / GIT_KEEP_FILE, "")
    return DEFAULT_SKILLS_DIR


def _handle_reinit(
    git_root: Path, config: SourceConfig, requested: _RequestedChanges
) -> None:
    old_name = config.name
    effective_name = requested.name if requested.name is not None else old_name
    is_rename = effective_name != old_name
    changes: list[str] = []

    if is_rename:
        _rename_installed_skills(old_name, effective_name)
        config.name = effective_name
        changes.append(_change_line("name", old_name, effective_name))

    if requested.branch is not None and requested.branch != config.branch:
        changes.append(_change_line("branch", config.branch, requested.branch))
        config.branch = requested.branch

    if (
        requested.skills_dirs is not None
        and requested.skills_dirs != config.skills_dirs
    ):
        changes.append(_dirs_change_line(config.skills_dirs, requested.skills_dirs))
        config.skills_dirs = requested.skills_dirs
        _note_empty_skills_dirs(git_root, requested.skills_dirs)

    if changes:
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


def _change_line(label: str, old: _ChangeValue, new: _ChangeValue) -> str:
    return f"  {label}: {fmt_data(old)} → {fmt_data(new)}"


def _dirs_change_line(old: Sequence[str], new: Sequence[str]) -> str:
    # TODO: multiple dirs in a single line looks ugly, need to split them to
    #       multiple lines

    # pure reorder is a real change and must not collapse to an identical-looking line
    return f"  dirs: {_join_ordered(old)} → {_join_ordered(new)}"


def _join_ordered(dirs: Sequence[str]) -> str:
    return ", ".join(fmt_data(d) for d in dirs)


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

        result = load_source_config(entry.repo_root)
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
