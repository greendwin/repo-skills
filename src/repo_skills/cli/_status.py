from __future__ import annotations

from pathlib import Path
from typing import Annotated, NamedTuple, TypeAlias

import typer

from repo_skills.config import (
    Baseline,
    ProviderRegistry,
    SkillManifest,
    SourceBrokenError,
    SourceRegistry,
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
)
from repo_skills.console import console, fmt_data, fmt_ident
from repo_skills.errors import AppError, NoopError
from repo_skills.git import ensure_on_branch

from ._app import app
from ._deps import resolve_git_repo

SkillsBySource: TypeAlias = dict[str, list[str]]
SourceSkillIndex: TypeAlias = dict[str, set[str]]


class UntrackedEntry(NamedTuple):
    name: str
    provider: str
    source_match: str


UntrackedLookup: TypeAlias = dict[str, list[str]]


def _build_untracked_lookup(untracked: list[UntrackedEntry]) -> UntrackedLookup:
    result: UntrackedLookup = {}
    for name, pname, source_match in untracked:
        if source_match:
            result.setdefault(name, []).append(pname)
    return result


@app.command(help="Show status of installed skills.")
def status(
    *,
    sync: Annotated[
        bool,
        typer.Option("--sync", help="Pull source repos before checking."),
    ] = False,
) -> None:
    manifest = load_skill_manifest()
    source_registry = load_source_registry()
    provider_registry = load_provider_registry()

    installed_by_source = _group_installed_by_source(manifest)
    available_by_source, all_source_skills = _scan_sources(
        source_registry, installed_by_source, sync=sync
    )
    untracked = _collect_untracked(manifest, provider_registry, all_source_skills)
    untracked_lookup = _build_untracked_lookup(untracked)

    all_names: list[str] = []
    for names in installed_by_source.values():
        all_names.extend(names)
    for names in available_by_source.values():
        all_names.extend(names)
    for name, _, _ in untracked:
        all_names.append(name)

    name_width = max((len(n) for n in all_names), default=0)
    provider_width = max((len(p.name) for p in provider_registry.providers), default=0)

    has_output = _print_source_sections(
        provider_registry,
        source_registry,
        manifest,
        installed_by_source=installed_by_source,
        available_by_source=available_by_source,
        name_width=name_width,
        provider_width=provider_width,
        untracked_lookup=untracked_lookup,
    )

    has_output |= _print_untracked_section(untracked, name_width, provider_width)

    if not has_output:
        raise NoopError("[dim]No skills found.[/dim]")


def _group_installed_by_source(manifest: SkillManifest) -> SkillsBySource:
    result: SkillsBySource = {}
    for skill_name, entry in manifest.skills.items():
        if not entry.detached:
            result.setdefault(entry.source, []).append(skill_name)

    return result


def _scan_sources(
    source_registry: SourceRegistry,
    installed_by_source: SkillsBySource,
    *,
    sync: bool = False,
) -> tuple[SkillsBySource, SourceSkillIndex]:
    available_by_source: SkillsBySource = {}
    all_source_skills: SourceSkillIndex = {}

    for source_name in source_registry.sources:
        try:
            # try to load source without skills parsing,
            # to make sure it's not broken
            source = source_registry.get_source(source_name, load_skills=False)
        except SourceBrokenError:
            available_by_source[source_name] = []
            all_source_skills[source_name] = set()
            continue

        git = resolve_git_repo(source.repo_root)
        target_branch = source.get_branch(git)
        try:
            ensure_on_branch(git, target_branch, pull=sync, require_clean=False)
        except AppError:
            if console.debug:
                console.print_exception()

            console.print(
                f"[yellow]Warning[/yellow]: {fmt_ident(source_name)} repo is dirty\n"
                f"Showing skills from {fmt_data(git.current_branch())}"
                f" instead of {fmt_data(target_branch)}"
            )

        # load skills on correct branch
        source = source_registry.get_source(source_name, load_skills=True)

        all_source_skills[source_name] = set(source.skills)
        already_installed = set(installed_by_source.get(source_name, []))
        available = [s for s in source.skills if s not in already_installed]
        if available:
            available_by_source[source_name] = available

    return available_by_source, all_source_skills


def _collect_untracked(
    manifest: SkillManifest,
    providers: ProviderRegistry,
    all_source_skills: SourceSkillIndex,
) -> list[UntrackedEntry]:
    installed_names = {
        name for name, skill in manifest.skills.items() if not skill.detached
    }
    all_known: set[str] = set()
    for source_skills in all_source_skills.values():
        all_known |= source_skills

    result: list[UntrackedEntry] = []
    for provider in providers.providers:
        provider_dir = provider.install_path
        if not provider_dir.is_dir():
            continue

        for child in sorted(provider_dir.iterdir()):
            if not child.is_dir():
                continue

            skill_name = child.name
            if skill_name in installed_names:
                continue

            if skill_name not in all_known:
                result.append(UntrackedEntry(skill_name, provider.name, ""))
                continue

            source_match = next(
                sn for sn, skills in all_source_skills.items() if skill_name in skills
            )
            result.append(UntrackedEntry(skill_name, provider.name, source_match))

    return result


def _untracked_hint(skill_name: str, lookup: UntrackedLookup) -> str:
    providers = lookup.get(skill_name)
    if not providers:
        return ""
    return f"  [dim](untracked in {', '.join(providers)})[/dim]"


def _print_source_sections(
    provider_registry: ProviderRegistry,
    source_registry: SourceRegistry,
    manifest: SkillManifest,
    *,
    installed_by_source: SkillsBySource,
    available_by_source: SkillsBySource,
    name_width: int,
    provider_width: int,
    untracked_lookup: UntrackedLookup,
) -> bool:
    all_sources = sorted(
        set(installed_by_source.keys()) | set(available_by_source.keys())
    )

    has_output = False

    for source_name in all_sources:
        try:
            _ = source_registry.get_source(source_name, load_skills=False)
            console.print(f"[yellow]Source[/yellow] {fmt_ident(source_name)}")
        except SourceBrokenError:
            console.print(
                f"[yellow]Source[/yellow] {fmt_ident(source_name)}  [red](broken)[/red]"
            )

        has_output = True

        for skill_name in sorted(installed_by_source.get(source_name, [])):
            entry = manifest.skills[skill_name]
            for provider in provider_registry.providers:
                installed_path = provider.install_path / skill_name
                divergence = _check_divergence(installed_path, entry.baseline)
                console.print(
                    f"  {skill_name:<{name_width}}"
                    f"  [dim]{provider.name:<{provider_width}}[/dim]"
                    f"  {divergence}"
                )

        for skill_name in sorted(available_by_source.get(source_name, [])):
            hint = _untracked_hint(skill_name, untracked_lookup)
            if hint:
                console.print(
                    f"  {skill_name:<{name_width}}  [cyan]mergeable[/cyan]{hint}"
                )
            else:
                console.print(
                    f"  {skill_name:<{name_width}}  [blue]available[/blue]{hint}"
                )

    return has_output


def _print_untracked_section(
    untracked: list[UntrackedEntry],
    name_width: int,
    provider_width: int,
) -> bool:
    orphans = sorted((e for e in untracked if not e.source_match), key=lambda e: e.name)
    if not orphans:
        return False

    console.print("")
    console.print("[yellow]Untracked[/yellow]")
    for skill in orphans:
        console.print(
            f"  {skill.name:<{name_width}}"
            f"  [dim]{skill.provider:<{provider_width}}[/dim]"
            f"  [dim magenta]orphan[/dim magenta]"
        )

    return True


def _check_divergence(installed_path: Path, baseline: Baseline | None) -> str:
    if not installed_path.exists():
        return "[red]missing[/red]"

    if baseline is None:
        return "[dim]untracked[/dim]"

    current = compute_file_hashes(installed_path)
    if current == baseline.files:
        return "[green]synced[/green]"

    return "[yellow]modified[/yellow]"
