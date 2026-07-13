from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated, Optional

import typer
from cli_error import CliError, CliExit, render_template
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
from repo_skills.console import reporter
from repo_skills.discovery import (
    DetectKind,
    detect_skills_dir,
    has_any_skill,
    normalize_repo_dir,
    path_within,
)
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
        raise _repo_error(
            git, "Branch [id]{branch}[/id] not found.", branch=requested.branch
        )

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
    # collapse nested/overlapping entries so each subtree is walked at most once;
    # input order is preserved so the active (first) surviving dir keeps priority
    accepted: list[Path] = []
    for skills_dir in skills_dirs:
        resolved = normalize_repo_dir(git.root, skills_dir)
        if resolved is None:
            raise _repo_error(
                git, "Skills dir [data]{dir}[/data] escapes the repo.", dir=skills_dir
            )

        # exact repeat: silent dedup, not a nesting (no Note); compare component-wise
        # so cross-flavour paths still collapse
        if any(a.parts == resolved.parts for a in accepted):
            continue

        # strictly inside an already-accepted dir: drop and note. both operands are
        # already normalize_repo_dir-resolved, so containment is over canonical paths
        container = next((a for a in accepted if path_within(resolved, a)), None)
        if container is not None:
            _note_nested_skills_dir(git.root, resolved, container)
            continue

        # absorb any already-accepted dirs strictly inside this broader one
        kept: list[Path] = []
        for a in accepted:
            if path_within(a, resolved):
                _note_nested_skills_dir(git.root, a, resolved)
            else:
                kept.append(a)
        accepted = [*kept, resolved]

    return [rel_posix(a, git.root) for a in accepted]


def _note_nested_skills_dir(repo_root: Path, dropped: Path, container: Path) -> None:
    reporter.print(
        "[dim]Note:[/dim] [path]{dropped}[/path] "
        "[dim]is inside [path]{container}[/path]; "
        "ignoring the duplicate.[/dim]",
        dropped=rel_posix(dropped, repo_root),
        container=rel_posix(container, repo_root),
    )


def _repo_error(git: GitRepo, msg: str, /, **args: object) -> CliError:
    return CliError(msg, **args).prop_path("repo", git.root)


def _note_empty_skills_dirs(repo_root: Path, skills_dirs: Sequence[str]) -> None:
    for rel in skills_dirs:
        if not _dir_has_skills(repo_root / rel):
            reporter.print(
                "[dim]Note:[/dim] [path]{rel}[/path] "
                "[dim]currently has no skills.[/dim]",
                rel=rel,
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

    reporter.print("Initialized source [id]{name}[/id].", name=source_name)


def _detect_fresh_skills_dir(git: GitRepo) -> str:
    detected = detect_skills_dir(git.root)
    if detected.kind is DetectKind.SINGLE:
        return rel_posix(detected.require_path(), git.root)

    if detected.kind is DetectKind.AMBIGUOUS:
        raise _repo_error(
            git,
            "Skills are spread across the repo root; cannot auto-detect a "
            "skills directory. Re-run with explicit "
            "[data]--skills-dir[/data] values.",
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

    if not was_registered:
        reporter.print("Registered source [id]{name}[/id].", name=effective_name)
    elif changes:
        reporter.print("Updated source [id]{name}[/id].", name=effective_name)
    else:
        reporter.print(
            "Source [id]{name}[/id] already initialized.", name=effective_name
        )

    for change in changes:
        reporter.print(change)


def _change_line(label: str, old: _ChangeValue, new: _ChangeValue) -> str:
    # pre-render: reporter.print gets a ready markup string, no format args
    return render_template(
        "  {label}: [data]{old}[/data] → [data]{new}[/data]",
        label=label,
        old=old,
        new=new,
    )


def _dirs_change_line(old: Sequence[str], new: Sequence[str]) -> str:
    # TODO: multiple dirs in a single line looks ugly, need to split them to
    #       multiple lines

    # stored order matters: first dir is the active write-back target, so a pure
    # reorder is a real change — don't sort
    return render_template(
        "  dirs: [data]{old}[/data] → [data]{new}[/data]",
        old=_join_ordered(old),
        new=_join_ordered(new),
    )


def _join_ordered(dirs: Sequence[str]) -> str:
    return ", ".join(dirs)


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
        raise CliExit("[dim]No sources registered.[/dim]")

    reporter.print("[yellow]Skill sources[/yellow]")
    width = max(len(n) for n in registry.sources)
    width = max(width, 16)
    for name, entry in registry.sources.items():
        message = f"  [white]{name:<{width}}[/white]  [cyan]{entry.repo_root}[/cyan]"

        if not entry.repo_root.exists():
            message += "  [red](missing)[/red]"
            reporter.print(message)
            continue

        result = load_source_config(entry.repo_root)
        if result.state is ConfigState.OK:
            if result.cfg.branch:
                message += f"  [dim](branch: {result.cfg.branch})[/dim]"
        elif result.state is ConfigState.BROKEN:
            message += "  [red](broken)[/red]"
        else:
            message += "  [red](not-inited)[/red]"

        reporter.print(message)


@source_app.command(name="remove", help="Remove a source from registry.")
def source_remove(
    source_name: str = typer.Argument(help="Name of the source to remove."),
    force: bool = typer.Option(
        False, "--force", help="Remove even if skills are installed (unregisters them)."
    ),
) -> None:
    source_registry = load_source_registry()

    if source_name not in source_registry.sources:
        raise CliError("Source [id]{name}[/id] not found.", name=source_name)

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
            raise CliError("Cannot remove a source with installed skills.")

        for skill_name in matching:
            manifest.unregister_skill(skill_name)
        save_skill_manifest(manifest)

        # BUG: comma should not be included to [id]
        names = ", ".join(sorted(matching))
        reporter.print(
            "Unregistered [data]{count}[/data] skill(s): [id]{names}[/id].",
            count=len(matching),
            names=names,
        )

    source_registry.unregister_source(source_name)
    save_source_registry(source_registry)

    reporter.print(
        "Removed source [id]{name}[/id] at [path]{path}[/path].",
        name=source_name,
        path=repo_root,
    )
