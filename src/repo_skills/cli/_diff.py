from __future__ import annotations

import difflib
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.markup import escape

from repo_skills.config import (
    InstalledSkill,
    Source,
    SourceSkill,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
)
from repo_skills.console import console, fmt_ident
from repo_skills.errors import AppError, FileNotInCommitError, NoopError

from ._app import app
from ._deps import resolve_git_repo
from ._utils import find_skill_in_provider, resolve_untracked


@app.command(help="Show diff of installed skill against baseline.")
def diff(
    *,
    skill_name: Annotated[str, typer.Argument(help="Skill to diff.")],
    from_provider: Annotated[
        Optional[str],
        typer.Option("--from", help="Provider (required when ambiguous)."),
    ] = None,
) -> None:
    provider_registry = load_provider_registry()
    source_registry = load_source_registry()
    manifest = load_skill_manifest()

    provider_obj = None
    if from_provider:
        provider_obj = provider_registry.require(from_provider)

    provider_obj = find_skill_in_provider(provider_registry, provider_obj, skill_name)

    installed_path = provider_obj.install_path / skill_name

    entry = manifest.skills.get(skill_name)

    if entry is not None:
        try:
            source = source_registry.get_source(entry.source, load_skills=True)
        except AppError:
            raise AppError(
                f"Source {fmt_ident(entry.source)} for skill"
                f" {fmt_ident(skill_name)} is no longer registered."
            ) from None
        skill = source.get_skill(skill_name)

        if entry.baseline:
            ref_files, all_files = _read_baseline_files(
                source, skill, entry, installed_path
            )
        else:
            ref_files, all_files = _read_source_files(source, skill, installed_path)
    else:
        untracked = resolve_untracked(
            provider_registry,
            source_registry,
            skill_name=skill_name,
            provider=provider_obj,
        )
        if untracked is None:
            raise AppError(f"Cannot find source for {fmt_ident(skill_name)}.")

        ref_files, all_files = _read_source_files(
            untracked.source, untracked.skill, installed_path
        )

    _output_diff(skill_name, ref_files, all_files, installed_path)


def _collect_files(path: Path) -> set[str]:
    return {str(f.relative_to(path)) for f in path.rglob("*") if f.is_file()}


def _read_file(path: Path) -> list[str]:
    return path.read_bytes().decode(errors="replace").splitlines(keepends=True)


def _read_baseline_files(
    source: Source,
    skill: SourceSkill,
    entry: InstalledSkill,
    installed_path: Path,
) -> tuple[dict[str, list[str]], set[str]]:
    assert entry.baseline is not None

    git = resolve_git_repo(source.repo_root)
    commit = entry.baseline.commit

    all_files = _collect_files(installed_path)
    all_files.update(entry.baseline.files.keys())

    ref_files: dict[str, list[str]] = {}
    for rel_file in all_files:
        full_path = f"{skill.rel_path}/{rel_file}"
        try:
            data = git.get_file_at_commit(commit, full_path)
            ref_files[rel_file] = data.decode(errors="replace").splitlines(
                keepends=True
            )
        except FileNotInCommitError:
            ref_files[rel_file] = []

    return ref_files, all_files


def _read_source_files(
    source: Source,
    skill: SourceSkill,
    installed_path: Path,
) -> tuple[dict[str, list[str]], set[str]]:
    all_files = _collect_files(installed_path)
    source_skill_dir = source.repo_root / skill.rel_path
    if source_skill_dir.is_dir():
        all_files.update(_collect_files(source_skill_dir))

    ref_files: dict[str, list[str]] = {}
    for rel_file in all_files:
        disk_path = source_skill_dir / rel_file
        if disk_path.exists():
            ref_files[rel_file] = _read_file(disk_path)
        else:
            ref_files[rel_file] = []

    return ref_files, all_files


def _output_diff(
    skill_name: str,
    ref_files: dict[str, list[str]],
    all_files: set[str],
    installed_path: Path,
) -> None:
    has_diff = False

    for rel_file in sorted(all_files):
        ref_lines = ref_files.get(rel_file, [])
        installed_file = installed_path / rel_file
        if installed_file.exists():
            installed_lines = _read_file(installed_file)
        else:
            installed_lines = []

        diff_lines = list(
            difflib.unified_diff(
                ref_lines,
                installed_lines,
                fromfile=f"a/{skill_name}/{rel_file}",
                tofile=f"b/{skill_name}/{rel_file}",
            )
        )

        if not diff_lines:
            continue

        has_diff = True
        for line in diff_lines:
            _print_diff_line(line)

    if not has_diff:
        raise NoopError(f"{fmt_ident(skill_name)} has no differences.")


def _print_diff_line(line: str) -> None:
    text = line.rstrip("\n")
    safe = escape(text)

    if console.no_color:
        console.print(safe)
        return

    if text.startswith("+++") or text.startswith("---"):
        console.print(f"[bold]{safe}[/bold]")
    elif text.startswith("@@"):
        console.print(f"[cyan]{safe}[/cyan]")
    elif text.startswith("+"):
        console.print(f"[green]{safe}[/green]")
    elif text.startswith("-"):
        console.print(f"[red]{safe}[/red]")
    else:
        console.print(f"[dim]{safe}[/dim]")
