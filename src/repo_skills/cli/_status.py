from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Annotated, NamedTuple, TypeAlias

import typer

from repo_skills.config import (
    Baseline,
    ConfigContext,
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceBrokenError,
    SourceRegistry,
    compute_file_hashes,
    load_config_context,
)
from repo_skills.console import console, fmt_data, fmt_ident
from repo_skills.errors import AppError, NoopError
from repo_skills.git import ensure_on_branch

from ._app import app
from ._deps import resolve_git_repo

SkillsBySource: TypeAlias = dict[str, list[str]]
SourceSkillIndex: TypeAlias = dict[str, set[str]]

STATUS_MISSING = "[red]missing[/red]"
STATUS_SYNCED = "[green]synced[/green]"
STATUS_MODIFIED = "[yellow]modified[/yellow]"
STATUS_OUTDATED = "[blue]outdated[/blue]"
STATUS_MERGEABLE = "[cyan]mergeable[/cyan]"
STATUS_AVAILABLE = "[blue]available[/blue]"
STATUS_ORPHAN = "[dim magenta]orphan[/dim magenta]"


class UntrackedEntry(NamedTuple):
    name: str
    provider: str
    source_match: str


@app.command(help="Show status of installed skills.")
def status(
    *,
    sync: Annotated[
        bool,
        typer.Option("--sync", help="Pull source repos before checking."),
    ] = False,
) -> None:
    ctx = load_config_context()

    # TODO: rework all this method to typed structures (too many raw strings now)
    #       (e.g. don't store skill_name, but manifest entry itself, and so on)
    installed_by_source = _group_installed_by_source(ctx.manifest)
    available_by_source, all_source_skills, loaded_sources = _scan_sources(
        ctx.source_registry, installed_by_source, sync=sync
    )
    outdated = _compute_outdated(ctx.manifest, installed_by_source, loaded_sources)
    untracked = _collect_untracked(
        ctx.manifest, ctx.provider_registry, all_source_skills
    )

    all_names: list[str] = []
    for names in installed_by_source.values():
        all_names.extend(names)
    for names in available_by_source.values():
        all_names.extend(names)
    for name, _, _ in untracked:
        all_names.append(name)

    name_width = max((len(n) for n in all_names), default=0)
    provider_names = [p.name for p in ctx.provider_registry.providers]
    provider_width = len(", ".join(provider_names)) if provider_names else 0

    view = _StatusView(
        provider_registry=ctx.provider_registry,
        source_registry=ctx.source_registry,
        manifest=ctx.manifest,
        installed_by_source=installed_by_source,
        available_by_source=available_by_source,
        name_width=name_width,
        provider_width=provider_width,
        outdated=outdated,
        mergeable_providers=_mergeable_providers(untracked),
    )

    all_sources = sorted(
        set(installed_by_source.keys()) | set(available_by_source.keys())
    )
    orphans = sorted((p for p in untracked if not p.source_match), key=lambda x: x.name)

    sections: list[Callable[[], None]] = [
        partial(_render_source_section, view, source_name)
        for source_name in all_sources
    ]
    if orphans:
        sections.append(
            partial(_print_untracked_section, orphans, name_width, provider_width)
        )

    if not sections:
        raise NoopError("[dim]No skills found.[/dim]")

    for index, render_section in enumerate(sections):
        if index:
            console.print("")
        render_section()


def _group_installed_by_source(manifest: SkillManifest) -> SkillsBySource:
    result: SkillsBySource = defaultdict(list)
    for skill_name, entry in manifest.skills.items():
        if not entry.detached:
            result[entry.source].append(skill_name)

    return result


def _scan_sources(
    source_registry: SourceRegistry,
    installed_by_source: SkillsBySource,
    *,
    sync: bool = False,
) -> tuple[SkillsBySource, SourceSkillIndex, dict[str, Source]]:
    # TODO: rework ret type to named tuple
    available_by_source: SkillsBySource = {}
    all_source_skills: SourceSkillIndex = {}
    loaded_sources: dict[str, Source] = {}

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
        loaded_sources[source_name] = source

        all_source_skills[source_name] = set(source.skills)
        already_installed = set(installed_by_source.get(source_name, []))
        available = [s for s in source.skills if s not in already_installed]
        if available:
            available_by_source[source_name] = available

    return available_by_source, all_source_skills, loaded_sources


def _compute_outdated(
    manifest: SkillManifest,
    installed_by_source: SkillsBySource,
    loaded_sources: dict[str, Source],
) -> set[str]:
    outdated: set[str] = set()
    for source_name, skill_names in installed_by_source.items():
        source = loaded_sources.get(source_name)
        if source is None:
            continue

        git = resolve_git_repo(source.repo_root)
        target_branch = source.get_branch(git)
        for skill_name in skill_names:
            entry = manifest.skills[skill_name]
            if entry.baseline is None:
                continue

            source_skill = source.skills.get(skill_name)
            if source_skill is None:
                continue

            latest_commit = git.get_skill_commit(
                source_skill.rel_path, branch=target_branch
            )
            if not latest_commit:
                continue

            if entry.baseline.commit != latest_commit:
                outdated.add(skill_name)

    return outdated


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


def _print_skill_rows(
    skill_name: str,
    pairs: list[tuple[str, str]],
    name_width: int,
    provider_width: int,
) -> None:
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for provider_name, status_str in pairs:
        grouped[status_str].append(provider_name)

    for status_str, providers in grouped.items():
        joined = ", ".join(providers)
        console.print(
            f"  {skill_name:<{name_width}}"
            f"  [dim]{joined:<{provider_width}}[/dim]"
            f"  {status_str}"
        )


@dataclass
class _StatusView(ConfigContext):
    installed_by_source: SkillsBySource
    available_by_source: SkillsBySource
    name_width: int
    provider_width: int
    outdated: set[str]
    mergeable_providers: dict[str, list[str]]


def _mergeable_providers(untracked: list[UntrackedEntry]) -> dict[str, list[str]]:
    # skill_name -> provider names, for orphans that match a known source skill
    result: defaultdict[str, list[str]] = defaultdict(list)
    for name, pname, source_match in untracked:
        if source_match:
            result[name].append(pname)

    return result


def _render_source_section(view: _StatusView, source_name: str) -> None:
    try:
        _ = view.source_registry.get_source(source_name, load_skills=False)
        console.print(f"[yellow]Source[/yellow] {fmt_ident(source_name)}")
    except SourceBrokenError:
        console.print(
            f"[yellow]Source[/yellow] {fmt_ident(source_name)}  [red](broken)[/red]"
        )

    for skill_name in sorted(view.installed_by_source.get(source_name, [])):
        entry = view.manifest.skills[skill_name]
        pairs: list[tuple[str, str]] = []
        for provider in view.provider_registry.providers:
            installed_path = provider.install_path / skill_name
            divergence = _check_divergence(installed_path, entry.baseline)
            if skill_name in view.outdated and installed_path.exists():
                divergence = f"{divergence}, {STATUS_OUTDATED}"
            pairs.append((provider.name, divergence))

        _print_skill_rows(skill_name, pairs, view.name_width, view.provider_width)

    for skill_name in sorted(view.available_by_source.get(source_name, [])):
        providers = view.mergeable_providers.get(skill_name)
        if providers:
            pairs = [(p, STATUS_MERGEABLE) for p in providers]
        else:
            pairs = [("", STATUS_AVAILABLE)]

        _print_skill_rows(skill_name, pairs, view.name_width, view.provider_width)


def _print_untracked_section(
    orphans: list[UntrackedEntry],
    name_width: int,
    provider_width: int,
) -> None:
    # group orphans by skill name to collect providers
    orphan_providers: defaultdict[str, list[str]] = defaultdict(list)
    for entry in orphans:
        orphan_providers[entry.name].append(entry.provider)

    console.print("[yellow]Untracked[/yellow]")
    for skill_name, providers in orphan_providers.items():
        _print_skill_rows(
            skill_name,
            [(p, STATUS_ORPHAN) for p in providers],
            name_width,
            provider_width,
        )


def _check_divergence(installed_path: Path, baseline: Baseline | None) -> str:
    if not installed_path.exists():
        return STATUS_MISSING

    if baseline is None:
        return STATUS_MERGEABLE

    current = compute_file_hashes(installed_path)
    if current == baseline.files:
        return STATUS_SYNCED

    return STATUS_MODIFIED
