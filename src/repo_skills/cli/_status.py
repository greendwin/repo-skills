from __future__ import annotations

from pathlib import Path
from typing import Annotated, NamedTuple, TypeAlias

import typer

from repo_skills.config import (
    ProviderRegistry,
    SkillManifest,
    SourceBrokenError,
    SourceRegistry,
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
)
from repo_skills.errors import NoopError
from repo_skills.utils import fmt_ident

from ._app import app
from ._deps import resolve_git_repo
from ._utils import echo

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

    if sync:
        for source_entry in source_registry.sources.values():
            git = resolve_git_repo(source_entry.repo_root)
            git.pull()

    installed_by_source = _group_installed_by_source(manifest)
    available_by_source, all_source_skills = _scan_sources(
        source_registry, installed_by_source
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
    provider_width = max((len(n) for n in provider_registry.providers), default=0)

    has_output = _print_source_sections(
        source_registry,
        installed_by_source,
        available_by_source,
        manifest,
        provider_registry,
        name_width,
        provider_width,
        untracked_lookup,
    )

    has_output |= _print_untracked_section(untracked, name_width, provider_width)

    if not has_output:
        raise NoopError("[dim]No skills found.[/dim]")


def _group_installed_by_source(manifest: SkillManifest) -> SkillsBySource:
    result: SkillsBySource = {}
    for skill_name, entry in manifest.skills.items():
        result.setdefault(entry.source, []).append(skill_name)
    return result


def _scan_sources(
    source_registry: SourceRegistry,
    installed_by_source: SkillsBySource,
) -> tuple[SkillsBySource, SourceSkillIndex]:
    available_by_source: SkillsBySource = {}
    all_source_skills: SourceSkillIndex = {}

    for source_name, source_entry in source_registry.sources.items():
        # TODO: show corresponding source as broken in status list
        try:
            source = source_registry.get_source(source_name, load_skills=True)
        except SourceBrokenError:
            available_by_source[source_name] = []
            all_source_skills[source_name] = set()
            continue

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
    installed_names = set(manifest.skills.keys())
    all_known: set[str] = set()
    for source_skills in all_source_skills.values():
        all_known |= source_skills

    result: list[UntrackedEntry] = []
    for pname, provider in providers.providers.items():
        provider_dir = provider.install_path
        if not provider_dir.is_dir():
            continue

        for child in sorted(provider_dir.iterdir()):
            if not child.is_dir():
                continue

            name = child.name
            if name in installed_names:
                continue

            if name not in all_known:
                result.append(UntrackedEntry(name, pname, ""))
                continue

            source_match = next(
                sn for sn, skills in all_source_skills.items() if name in skills
            )
            result.append(UntrackedEntry(name, pname, source_match))

    return result


def _untracked_hint(skill_name: str, lookup: UntrackedLookup) -> str:
    providers = lookup.get(skill_name)
    if not providers:
        return ""
    return f"  [dim](untracked in {', '.join(providers)})[/dim]"


def _print_source_sections(
    source_registry: SourceRegistry,
    installed_by_source: SkillsBySource,
    available_by_source: SkillsBySource,
    manifest: SkillManifest,
    providers: ProviderRegistry,
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
        except SourceBrokenError:
            echo(
                f"[yellow]Source[/yellow] {fmt_ident(source_name)} - [red]broken[/red]"
            )
            has_output = True
            continue

        echo(f"[yellow]Source[/yellow] {fmt_ident(source_name)}")
        has_output = True

        for skill_name in sorted(installed_by_source.get(source_name, [])):
            entry = manifest.skills[skill_name]
            for pname, provider in providers.providers.items():
                installed_path = provider.install_path / skill_name
                divergence = _check_divergence(installed_path, entry.files)
                echo(
                    f"  {skill_name:<{name_width}}"
                    f"  [dim]{pname:<{provider_width}}[/dim]"
                    f"  {divergence}"
                )

        for skill_name in sorted(available_by_source.get(source_name, [])):
            hint = _untracked_hint(skill_name, untracked_lookup)
            if hint:
                echo(f"  {skill_name:<{name_width}}  [cyan]mergeable[/cyan]{hint}")
            else:
                echo(f"  {skill_name:<{name_width}}  [cyan]available[/cyan]{hint}")

    return has_output


def _print_untracked_section(
    untracked: list[UntrackedEntry],
    name_width: int,
    provider_width: int,
) -> bool:
    orphans = sorted((e for e in untracked if not e.source_match), key=lambda e: e.name)
    if not orphans:
        return False

    echo("")
    echo("[yellow]Untracked[/yellow]")
    for skill in orphans:
        echo(
            f"  {skill.name:<{name_width}}"
            f"  [dim]{skill.provider:<{provider_width}}[/dim]"
            f"  [dim magenta]orphan[/dim magenta]"
        )

    return True


def _check_divergence(installed_path: Path, baseline: dict[str, str]) -> str:
    if not installed_path.exists():
        return "[red]missing[/red]"

    current = compute_file_hashes(installed_path)
    if current == baseline:
        return "[green]synced[/green]"

    return "[yellow]modified[/yellow]"
