from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.markup import escape

from repo_skills.config import (
    Baseline,
    InstalledSkill,
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceRegistry,
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
    save_skill_manifest,
)
from repo_skills.console import console, fmt_data, fmt_ident
from repo_skills.errors import AppError, NoopError
from repo_skills.git import ensure_on_branch, resolve_verified_commit

from ._app import app
from ._deps import resolve_git_repo


class _Status(Enum):
    UPDATED = auto()
    SKIPPED = auto()
    UP_TO_DATE = auto()


_STATUS_LABEL: dict[_Status, str] = {
    _Status.UPDATED: "[green]updated[/green]",
    _Status.UP_TO_DATE: "[blue]up-to-date[/blue]",
    _Status.SKIPPED: "[yellow]skipped[/yellow] [dim](modified)[/dim]",
}
_DETACHED = "[yellow]detached[/yellow] [dim](commit unreachable)[/dim]"
_RECOVERED = "[green]recovered[/green]"
_UNTRACKED = "[yellow]untracked[/yellow] [dim](need merge)[/dim]"


@app.command(help="Update installed skills from sources.")
def update(
    *,
    skill_names: Annotated[
        Optional[list[str]],
        typer.Argument(help="Skills to update (all if omitted)."),
    ] = None,
    source_names: Annotated[
        Optional[list[str]],
        typer.Option("--source", "-s", help="Update only skills from these sources."),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip git pull."),
    ] = False,
) -> None:
    providers = load_provider_registry()
    manifest = load_skill_manifest()
    source_registry = load_source_registry()

    to_update = _collect_skills_for_update(
        manifest,
        source_registry,
        skill_names=skill_names,
        source_names=source_names,
    )

    untracked = _scan_untracked_install_dirs(
        manifest,
        providers,
        skill_names=skill_names,
    )
    if untracked:
        eligible = _eligible_attach_sources(
            source_registry,
            to_update,
            skill_names=skill_names,
            source_names=source_names,
        )
        attach_candidates = _find_attach_candidates(untracked, eligible)
    else:
        attach_candidates = []

    if not to_update.skills and not attach_candidates:
        if source_names:
            raise NoopError(
                f"[dim]No skills installed from source {fmt_data(source_names)}.[/dim]"
            )
        raise NoopError("[dim]No skills installed.[/dim]")

    candidate_sources = frozenset(name for c in attach_candidates for name in c.sources)
    pull_sources = to_update.sources | candidate_sources

    source_branches: dict[str, str] = {}
    for source_name in sorted(source_registry.sources):
        if source_name not in pull_sources:
            continue

        registered = source_registry.get_source(source_name, load_skills=False)
        git = resolve_git_repo(registered.repo_root)
        branch = registered.get_branch(git)

        with console.running(f"Pulling {fmt_data(source_name)}"):
            ensure_on_branch(git, branch, pull=not offline)
            source_branches[source_name] = branch
            if offline:
                console.finish("[dim]skipped[/dim]")
            else:
                console.finish("[green]done[/green]")

    attached = _attach_skills(attach_candidates, manifest, source_branches)
    skills_to_update = {**to_update.skills, **attached}

    for skill_name, entry in skills_to_update.items():
        with console.running(f"Updating {fmt_data(skill_name)}"):
            try:
                report = _update_skill(
                    skill_name, entry, source_registry, providers, source_branches
                )
            except Exception as ex:
                if console.debug:
                    console.print_exception()
                console.print(f"[red]Error[/red]: {escape(str(ex))}")
                continue

            if isinstance(report, _SkillError):
                console.print(f"[red]Error[/red]: {report.message}")
                continue

            _print_skill_report(skill_name, report)

            baseline = None
            if entry.baseline:
                baseline = Baseline(
                    commit=entry.baseline.commit,
                    files=report.source_hashes,
                )

            manifest.register_skill(
                skill_name,
                source_name=entry.source,
                baseline=baseline,
                detached=report.detached,
            )

    save_skill_manifest(manifest)


@dataclass(frozen=True)
class _Targets:
    skills: dict[str, InstalledSkill]
    sources: frozenset[str]


def _collect_skills_for_update(
    manifest: SkillManifest,
    source_registry: SourceRegistry,
    *,
    skill_names: list[str] | None,
    source_names: list[str] | None,
) -> _Targets:
    skills: dict[str, InstalledSkill] = {}

    for name in skill_names or ():
        inst = manifest.skills.get(name)
        if inst is None:
            raise AppError(f"Skill {fmt_ident(name)} is not installed.")

        skills[name] = inst

    for name in source_names or ():
        # make sure this source exists
        _ = source_registry.get_source(name, load_skills=False)

    for name, skill in manifest.skills.items():
        if skill.source in (source_names or ()):
            skills[name] = skill

    if not skill_names and not source_names:
        skills = dict(manifest.skills)

    return _Targets(
        skills=skills,
        sources=frozenset(entry.source for entry in skills.values()),
    )


def _eligible_attach_sources(
    source_registry: SourceRegistry,
    to_update: _Targets,
    *,
    skill_names: list[str] | None,
    source_names: list[str] | None,
) -> dict[str, Source]:
    if not skill_names and not source_names:
        allowed: set[str] | None = None
    else:
        allowed = set(to_update.sources) | set(source_names or ())

    sources: dict[str, Source] = {}
    for source_name in source_registry.sources:
        if allowed is not None and source_name not in allowed:
            continue

        try:
            sources[source_name] = source_registry.get_source(
                source_name, load_skills=True
            )
        except AppError:
            # TODO: it can be not broken
            console.print(
                f"[yellow]Warning[/yellow]: skipping broken source "
                f"{fmt_ident(source_name)}"
            )
            continue

    return sources


def _scan_untracked_install_dirs(
    manifest: SkillManifest,
    providers: ProviderRegistry,
    *,
    skill_names: list[str] | None,
) -> dict[str, Path]:
    tracked = set(manifest.skills)

    untracked: dict[str, Path] = {}
    for provider in providers.providers:
        install_dir = provider.install_path
        if not install_dir.is_dir():
            continue

        for child in sorted(install_dir.iterdir()):
            if not child.is_dir():
                continue

            name = child.name
            if name in tracked or name in untracked:
                continue
            if skill_names and name not in skill_names:
                continue

            untracked[name] = child

    return untracked


@dataclass(frozen=True)
class _AttachCandidate:
    skill_name: str
    installed_hashes: dict[str, str]
    sources: dict[str, Source]


def _find_attach_candidates(
    untracked: dict[str, Path],
    eligible: dict[str, Source],
) -> list[_AttachCandidate]:
    candidates: list[_AttachCandidate] = []
    for name, child in untracked.items():
        name_matches = {
            source_name: source
            for source_name, source in eligible.items()
            if name in source.skills
        }
        if not name_matches:
            continue

        candidates.append(
            _AttachCandidate(
                skill_name=name,
                installed_hashes=compute_file_hashes(child),
                sources=name_matches,
            )
        )

    return candidates


def _attach_skills(
    candidates: list[_AttachCandidate],
    manifest: SkillManifest,
    source_branches: dict[str, str],
) -> dict[str, InstalledSkill]:
    attached: dict[str, InstalledSkill] = {}
    for candidate in candidates:
        entry = _attach_skill(candidate, manifest, source_branches)
        if entry is not None:
            attached[candidate.skill_name] = entry

    return attached


def _attach_skill(
    candidate: _AttachCandidate,
    manifest: SkillManifest,
    source_branches: dict[str, str],
) -> InstalledSkill | None:
    hash_matches: list[tuple[str, Source, dict[str, str]]] = []
    for source_name, source in candidate.sources.items():
        skill = source.skills.get(candidate.skill_name)
        if skill is None:
            continue

        source_hashes = compute_file_hashes(source.repo_root / skill.rel_path)
        if source_hashes == candidate.installed_hashes:
            hash_matches.append((source_name, source, source_hashes))

    if not hash_matches:
        return None
    
    if len(hash_matches) > 1:
        console.print(
            f"[yellow]Skipped[/yellow] skill {fmt_data(candidate.skill_name)}: "
            f"matched multiple sources "
            f"{fmt_data(sorted(name for name, _, _ in hash_matches))}"
        )
        return None

    source_name, source, source_hashes = hash_matches[0]
    skill = source.skills[candidate.skill_name]

    git = resolve_git_repo(source.repo_root)
    branch = source_branches.get(source_name, "")
    commit = resolve_verified_commit(
        git, skill.rel_path, branch=branch, require_commit=True
    )
    if commit is None:
        return None

    entry = manifest.register_skill(
        candidate.skill_name,
        source_name=source_name,
        baseline=Baseline(commit=commit, files=source_hashes),
        detached=False,
    )
    console.print(
        f"Attached skill {fmt_data(candidate.skill_name)} "
        f"(matched source {fmt_data(source_name)})"
    )
    return entry


@dataclass
class _SkillReport:
    provider_statuses: dict[str, _Status]
    source_hashes: dict[str, str]
    detached: bool
    recovered: bool = False
    newly_detached: bool = False


@dataclass
class _SkillError:
    message: str


def _update_skill(
    skill_name: str,
    entry: InstalledSkill,
    source_registry: SourceRegistry,
    providers: ProviderRegistry,
    source_branches: dict[str, str],
) -> _SkillReport | _SkillError:
    if entry.source not in source_registry.sources:
        return _SkillError(f"Source {fmt_ident(entry.source)} not found")

    source = source_registry.get_source(entry.source, load_skills=True)
    skill = source.skills.get(skill_name)
    if skill is None:
        return _SkillError("Skill removed from source")

    src = source.repo_root / skill.rel_path
    source_hashes = compute_file_hashes(src)
    provider_statuses: dict[str, _Status] = {}

    for provider in providers.providers:
        install_dir = provider.install_path
        dst = install_dir / skill_name

        if not dst.exists():
            install_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst)
            provider_statuses[provider.name] = _Status.UPDATED
            continue

        current_hashes = compute_file_hashes(dst)

        if current_hashes == source_hashes:
            provider_statuses[provider.name] = _Status.UP_TO_DATE
            continue

        if not entry.match_files(current_hashes):
            provider_statuses[provider.name] = _Status.SKIPPED
            continue

        shutil.rmtree(dst)
        shutil.copytree(src, dst)
        provider_statuses[provider.name] = _Status.UPDATED

    detached = entry.detached
    recovered = False
    newly_detached = False

    if entry.baseline and entry.source in source_branches:
        git = resolve_git_repo(source.repo_root)
        pinned = source_branches[entry.source]
        reachable = git.is_ancestor(entry.baseline.commit, pinned)
        if reachable and entry.detached:
            detached = False
            recovered = True
        elif not reachable and not entry.detached:
            detached = True
            newly_detached = True

    return _SkillReport(
        provider_statuses=provider_statuses,
        source_hashes=source_hashes,
        detached=detached,
        recovered=recovered,
        newly_detached=newly_detached,
    )


def _print_skill_report(skill_name: str, report: _SkillReport) -> None:
    unique = set(report.provider_statuses.values())

    if len(report.provider_statuses) > 1 and len(unique) > 1:
        if report.recovered:
            console.finish(_RECOVERED)
        elif report.newly_detached:
            console.finish(_DETACHED)
        elif report.detached:
            console.finish(_UNTRACKED)

        for prov_name, prov_status in report.provider_statuses.items():
            console.print(f"  {fmt_data(prov_name)}: {_STATUS_LABEL[prov_status]}")
        return

    if _Status.SKIPPED in unique and _Status.UPDATED not in unique:
        status = _STATUS_LABEL[_Status.SKIPPED]
    elif _Status.UPDATED in unique:
        status = _STATUS_LABEL[_Status.UPDATED]
    else:
        status = _STATUS_LABEL[_Status.UP_TO_DATE]

    if report.recovered:
        status = f"{status}, {_RECOVERED}"
    elif report.newly_detached:
        status = f"{status}, {_DETACHED}"
    elif report.detached:
        status = _UNTRACKED

    console.finish(status)
