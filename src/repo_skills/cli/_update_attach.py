from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.markup import escape

from repo_skills.config import (
    Baseline,
    InstalledSkill,
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceRegistry,
    compute_file_hashes,
)
from repo_skills.console import console, fmt_data, fmt_ident
from repo_skills.errors import AppError
from repo_skills.git import SyncedRepo, resolve_verified_commit


@dataclass(frozen=True)
class AttachCandidate:
    skill_name: str
    installed_hashes: dict[str, str]
    sources: dict[str, Source]


@dataclass(frozen=True)
class _SourceMatch:
    source_name: str
    source: Source
    hashes: dict[str, str]


def scan_untracked_install_dirs(
    manifest: SkillManifest,
    providers: ProviderRegistry,
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


def eligible_attach_sources(
    source_registry: SourceRegistry,
    source_names: list[str] | None,
) -> dict[str, Source]:
    sources: dict[str, Source] = {}
    for source_name in source_registry.sources:
        if source_names is not None and source_name not in source_names:
            continue

        try:
            sources[source_name] = source_registry.load_source(source_name)
        except AppError as ex:
            console.debug_traceback()

            console.print(
                f"[yellow]Warning[/yellow]: skipping broken source "
                f"{fmt_ident(source_name)}: {escape(str(ex))}"
            )

    return sources


def find_attach_candidates(
    untracked: dict[str, Path],
    eligible: dict[str, Source],
) -> list[AttachCandidate]:
    candidates: list[AttachCandidate] = []
    for name, child in untracked.items():
        name_matches = {
            source_name: source
            for source_name, source in eligible.items()
            if name in source.skills
        }
        if not name_matches:
            continue

        candidates.append(
            AttachCandidate(
                skill_name=name,
                installed_hashes=compute_file_hashes(child),
                sources=name_matches,
            )
        )

    return candidates


def attach_skills(
    candidates: list[AttachCandidate],
    source_repos: dict[str, SyncedRepo],
) -> dict[str, InstalledSkill]:
    attached: dict[str, InstalledSkill] = {}
    for candidate in candidates:
        entry = _attach_skill(candidate, source_repos)
        if entry is not None:
            attached[candidate.skill_name] = entry

    return attached


def _attach_skill(
    candidate: AttachCandidate,
    source_repos: dict[str, SyncedRepo],
) -> InstalledSkill | None:
    matches: list[_SourceMatch] = []
    for source_name, source in candidate.sources.items():
        skill = source.skills.get(candidate.skill_name)
        if skill is None:
            continue

        source_hashes = compute_file_hashes(source.repo_root / skill.rel_path)
        if source_hashes == candidate.installed_hashes:
            matches.append(_SourceMatch(source_name, source, source_hashes))

    if not matches:
        return None

    if len(matches) > 1:
        console.print(
            f"[yellow]Skipped[/yellow] skill {fmt_data(candidate.skill_name)}: "
            f"matched multiple sources "
            f"{fmt_data(sorted(m.source_name for m in matches))}"
        )
        return None

    match = matches[0]
    skill = match.source.skills[candidate.skill_name]

    repo = source_repos.get(match.source_name)
    if repo is None:
        # cannot attach skill if its source is not fully synced
        return None

    commit = resolve_verified_commit(repo, skill.rel_path)
    if commit is None:
        return None

    console.print(
        f"Attached skill {fmt_ident(candidate.skill_name)} "
        f"(matched source {fmt_data(match.source_name)})"
    )
    return InstalledSkill(
        source=match.source_name,
        baseline=Baseline(commit=commit, files=match.hashes),
    )
