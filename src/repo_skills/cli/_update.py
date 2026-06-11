from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum, auto
from typing import Annotated, NamedTuple, Optional

import typer

from repo_skills.config import (
    Baseline,
    ConfigContext,
    InstalledSkill,
    SkillManifest,
    SourceRegistry,
    compute_file_hashes,
    load_config_context,
    save_skill_manifest,
)
from repo_skills.console import console, fmt_data, fmt_ident
from repo_skills.errors import AppError, NoopError, render_error
from repo_skills.git import GitRepo, ensure_on_branch, resolve_verified_commit

from ._app import app
from ._deps import resolve_git_repo
from ._update_attach import (
    AttachCandidate,
    attach_skills,
    eligible_attach_sources,
    find_attach_candidates,
    scan_untracked_install_dirs,
)


class _Status(Enum):
    UPDATED = auto()
    SKIPPED = auto()
    UP_TO_DATE = auto()


_SYNCED_STATES = {_Status.UPDATED, _Status.UP_TO_DATE}


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
    ctx = load_config_context()

    targets = _collect_targets(
        ctx,
        skill_names=skill_names,
        source_names=source_names,
    )

    if not targets.skills and not targets.attach_candidates:
        if source_names:
            raise NoopError(
                f"[dim]No skills installed from source {fmt_data(source_names)}.[/dim]"
            )
        raise NoopError("[dim]No skills installed.[/dim]")

    source_branches, source_repos = _pull_sources(
        ctx.source_registry,
        targets.pull_sources,
        offline=offline,
    )

    attached = attach_skills(targets.attach_candidates, source_branches)
    skills_to_update = {**targets.skills, **attached}

    _run_updates(ctx, skills_to_update, source_branches, source_repos)
    save_skill_manifest(ctx.manifest)


@dataclass(frozen=True)
class _Targets:
    skills: dict[str, InstalledSkill]
    attach_candidates: list[AttachCandidate]
    pull_sources: frozenset[str]


def _collect_targets(
    ctx: ConfigContext,
    *,
    skill_names: list[str] | None,
    source_names: list[str] | None,
) -> _Targets:
    _validate_filters(ctx.manifest, ctx.source_registry, skill_names, source_names)

    skills = _select_skills(ctx.manifest, skill_names, source_names)
    tracked_sources = frozenset(p.source for p in skills.values())

    candidates = []
    untracked = scan_untracked_install_dirs(
        ctx.manifest, ctx.provider_registry, skill_names
    )
    if untracked:
        eligible = eligible_attach_sources(
            ctx.source_registry,
            source_names,
        )
        candidates = find_attach_candidates(untracked, eligible)

    candidate_sources = frozenset(name for c in candidates for name in c.sources)

    return _Targets(
        skills=skills,
        attach_candidates=candidates,
        pull_sources=tracked_sources | candidate_sources,
    )


def _validate_filters(
    manifest: SkillManifest,
    source_registry: SourceRegistry,
    skill_names: list[str] | None,
    source_names: list[str] | None,
) -> None:
    for name in skill_names or ():
        if name not in manifest.skills:
            # TODO: we can target untracked skill to try to auto-attach it
            raise AppError(f"Skill {fmt_ident(name)} is not installed.")

    for name in source_names or ():
        _ = source_registry.get_source(name, load_skills=False)


def _select_skills(
    manifest: SkillManifest,
    skill_names: list[str] | None,
    source_names: list[str] | None,
) -> dict[str, InstalledSkill]:
    if not skill_names and not source_names:
        return dict(manifest.skills)

    skills: dict[str, InstalledSkill] = {}

    for name in skill_names or ():
        skills[name] = manifest.skills[name]

    source_set = set(source_names or ())
    for name, skill in manifest.skills.items():
        if skill.source in source_set:
            skills[name] = skill

    return skills


class _PulledSources(NamedTuple):
    source_branches: dict[str, str]
    repos: dict[str, GitRepo]


def _pull_sources(
    source_registry: SourceRegistry,
    needed_sources: frozenset[str],
    *,
    offline: bool,
) -> _PulledSources:
    source_branches: dict[str, str] = {}
    source_repos: dict[str, GitRepo] = {}
    for source_name in sorted(source_registry.sources):
        if source_name not in needed_sources:
            continue

        registered = source_registry.get_source(source_name, load_skills=False)
        git = resolve_git_repo(registered.repo_root)
        branch = registered.get_branch(git)

        with console.running(
            f"Pulling {fmt_data(source_name)}", tty_subprocess=not offline
        ):
            try:
                ensure_on_branch(git, branch, pull=not offline)
            except Exception as ex:
                console.finish("[red]failed[/red]")
                render_error(ex)
                continue

            source_branches[source_name] = branch
            source_repos[source_name] = git
            if offline:
                console.finish("[dim]skipped[/dim]")
            else:
                console.finish("[green]done[/green]")

    return _PulledSources(source_branches, source_repos)


@dataclass
class _SkillReport:
    provider_statuses: dict[str, _Status]
    baseline: Baseline | None
    detached: bool
    recovered: bool = False
    newly_detached: bool = False


@dataclass(frozen=True)
class _BaselineDecision:
    baseline: Baseline | None
    detached: bool
    recovered: bool
    newly_detached: bool


def _advance_baseline(
    entry: InstalledSkill,
    *,
    in_sync: bool,
    latest_commit: str | None,
    source_hashes: dict[str, str],
    reachable: bool,
) -> _BaselineDecision:
    if in_sync:
        if latest_commit is not None:
            return _BaselineDecision(
                baseline=Baseline(commit=latest_commit, files=source_hashes),
                detached=False,
                recovered=entry.detached,
                newly_detached=False,
            )

        # latest commit unresolvable: refresh hashes, keep old commit
        baseline = (
            Baseline(commit=entry.baseline.commit, files=source_hashes)
            if entry.baseline
            else None
        )
        return _BaselineDecision(
            baseline=baseline,
            detached=entry.detached,
            recovered=False,
            newly_detached=False,
        )

    # skipped: baseline untouched
    if entry.baseline and not reachable and not entry.detached:
        return _BaselineDecision(
            baseline=entry.baseline,
            detached=True,
            recovered=False,
            newly_detached=True,
        )

    return _BaselineDecision(
        baseline=entry.baseline,
        detached=entry.detached,
        recovered=False,
        newly_detached=False,
    )


def _run_updates(
    ctx: ConfigContext,
    skills: dict[str, InstalledSkill],
    source_branches: dict[str, str],
    source_repos: dict[str, GitRepo],
) -> None:
    for skill_name, entry in skills.items():
        with console.running(f"Updating {fmt_data(skill_name)}"):
            try:
                report = _update_skill(
                    ctx, skill_name, entry, source_branches, source_repos
                )
            except Exception as ex:
                console.finish("[red]failed[/red]")
                render_error(ex)
                continue

            _print_skill_report(report)

            ctx.manifest.register_skill(
                skill_name,
                source_name=entry.source,
                baseline=report.baseline,
                detached=report.detached,
            )


def _update_skill(
    ctx: ConfigContext,
    skill_name: str,
    entry: InstalledSkill,
    source_branches: dict[str, str],
    source_repos: dict[str, GitRepo],
) -> _SkillReport:
    if entry.source not in ctx.source_registry.sources:
        raise AppError(f"Source {fmt_ident(entry.source)} not found")

    source = ctx.source_registry.get_source(entry.source, load_skills=True)
    skill = source.skills.get(skill_name)
    if skill is None:
        raise AppError("Skill removed from source")

    src = source.repo_root / skill.rel_path
    source_hashes = compute_file_hashes(src)
    provider_statuses: dict[str, _Status] = {}

    for provider in ctx.provider_registry.providers:
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
            # installed skill was modified, don't touch it
            provider_statuses[provider.name] = _Status.SKIPPED
            continue

        # skill is in sync with what was installed, update it to latest version
        shutil.rmtree(dst)
        shutil.copytree(src, dst)
        provider_statuses[provider.name] = _Status.UPDATED

    in_sync = all(s in _SYNCED_STATES for s in provider_statuses.values())

    pinned_branch = source_branches.get(entry.source)
    git = source_repos.get(entry.source)

    latest_commit = None
    if in_sync and pinned_branch is not None and git is not None:
        latest_commit = resolve_verified_commit(
            git, skill.rel_path, branch=pinned_branch
        )

    reachable = False
    if not in_sync and entry.baseline and pinned_branch is not None and git is not None:
        reachable = git.is_ancestor(entry.baseline.commit, pinned_branch)

    decision = _advance_baseline(
        entry,
        in_sync=in_sync,
        latest_commit=latest_commit,
        source_hashes=source_hashes,
        reachable=reachable,
    )

    return _SkillReport(
        provider_statuses=provider_statuses,
        baseline=decision.baseline,
        detached=decision.detached,
        recovered=decision.recovered,
        newly_detached=decision.newly_detached,
    )


def _print_skill_report(report: _SkillReport) -> None:
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
