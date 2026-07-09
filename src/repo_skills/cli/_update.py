from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Annotated, Optional

import typer
from cli_error import CliError, CliExit

from repo_skills.config import (
    Baseline,
    ConfigContext,
    InstalledSkill,
    ProviderRegistry,
    SkillManifest,
    SourceRegistry,
    compute_file_hashes,
    load_config_context,
    save_skill_manifest,
)
from repo_skills.console import fmt_data, fmt_ident, reporter
from repo_skills.git import (
    SyncedRepo,
    ensure_on_branch,
    find_commit_with_content,
    resolve_verified_commit,
)
from repo_skills.utils import overwrite_dir

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


class _Action(Enum):
    FRESH = auto()  # dst absent -> copy in
    UPDATE = auto()  # dst in sync with baseline but outdated -> overwrite
    UP_TO_DATE = auto()  # dst matches source
    SKIPPED = auto()  # dst locally modified -> leave alone


_ACTION_STATUS: dict[_Action, _Status] = {
    _Action.FRESH: _Status.UPDATED,
    _Action.UPDATE: _Status.UPDATED,
    _Action.UP_TO_DATE: _Status.UP_TO_DATE,
    _Action.SKIPPED: _Status.SKIPPED,
}


class _Detach(Enum):
    NONE = auto()  # attached before and after this update
    RECOVERED = auto()  # was detached, content-sync reattached it
    NEWLY_DETACHED = auto()  # was attached, baseline commit fell off history
    STILL_DETACHED = auto()  # remained detached (could not be reattached)


_SYNCED_STATES = {_Status.UPDATED, _Status.UP_TO_DATE}


_STATUS_LABEL: dict[_Status, str] = {
    _Status.UPDATED: "[green]updated[/green]",
    _Status.UP_TO_DATE: "[blue]up-to-date[/blue]",
    _Status.SKIPPED: "[yellow]skipped[/yellow] [dim](modified)[/dim]",
}
_DETACHED = "[yellow]detached[/yellow] [dim](commit unreachable)[/dim]"
_RECOVERED = "[green]recovered[/green]"
_UNTRACKED = "[yellow]untracked[/yellow] [dim](need merge)[/dim]"


def _source_unavailable_label(source: str) -> str:
    return (
        f"[yellow]skipped[/yellow] [dim](source {fmt_ident(source)} unavailable)[/dim]"
    )


_TRANSITION_LABEL: dict[_Detach, str] = {
    _Detach.RECOVERED: _RECOVERED,
    _Detach.NEWLY_DETACHED: _DETACHED,
    _Detach.STILL_DETACHED: _UNTRACKED,
}


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
            raise CliExit(
                f"[dim]No skills installed from source {fmt_data(source_names)}.[/dim]"
            )
        raise CliExit("[dim]No skills installed.[/dim]")

    source_repos = _sync_source_repos(
        ctx.source_registry,
        targets.pull_sources,
        offline=offline,
    )

    attached = attach_skills(targets.attach_candidates, source_repos)
    skills_to_update = {**targets.skills, **attached}

    _run_updates(ctx, skills_to_update, source_repos)
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
            raise CliError(f"Skill {fmt_ident(name)} is not installed.")

    for name in source_names or ():
        _ = source_registry.get_source_no_skills(name)


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


def _sync_source_repos(
    source_registry: SourceRegistry,
    needed_sources: frozenset[str],
    *,
    offline: bool,
) -> dict[str, SyncedRepo]:
    source_repos = {}
    for source_name in sorted(source_registry.sources):
        if source_name not in needed_sources:
            continue

        # note: request source without skills to avoid scanning them on wrong branch
        registered = source_registry.get_source_no_skills(source_name)
        git = resolve_git_repo(registered.repo_root)
        branch = registered.get_branch(git)

        with reporter.running(
            f"Pulling {fmt_data(source_name)}", tty_subprocess=not offline
        ):
            try:
                repo = ensure_on_branch(git, branch, pull=not offline)
            except Exception as ex:
                reporter.finish("[red]failed[/red]")
                reporter.report_error(ex)
                continue

            source_repos[source_name] = repo
            if offline:
                reporter.finish("[dim]skipped[/dim]")
            else:
                reporter.finish("[green]done[/green]")

    return source_repos


@dataclass(frozen=True)
class _SkillReport:
    provider_statuses: dict[str, _Status]
    baseline: Baseline | None
    transition: _Detach

    @property
    def detached(self) -> bool:
        return self.transition in (_Detach.NEWLY_DETACHED, _Detach.STILL_DETACHED)


def _run_updates(
    ctx: ConfigContext,
    skills: dict[str, InstalledSkill],
    source_repos: dict[str, SyncedRepo],
) -> None:
    for skill_name, entry in skills.items():
        with reporter.running(f"Updating {fmt_data(skill_name)}"):
            repo = source_repos.get(entry.source)
            if repo is None:
                reporter.finish(_source_unavailable_label(entry.source))
                continue

            try:
                outcome = _update_skill(ctx, entry, skill_name, repo)
            except Exception as ex:
                reporter.finish("[red]failed[/red]")
                reporter.report_error(ex)
                continue

            _print_skill_report(outcome)

            ctx.manifest.register_skill(
                skill_name,
                source_name=entry.source,
                baseline=outcome.baseline,
                detached=outcome.detached,
            )


def _update_skill(
    ctx: ConfigContext, entry: InstalledSkill, skill_name: str, repo: SyncedRepo
) -> _SkillReport:
    source = ctx.source_registry.load_source(entry.source)
    skill = source.skills.get(skill_name)
    if skill is None:
        # TODO: should we mark this skill as detached instead of reporting an error?
        raise CliError("Skill removed from source")

    src = source.repo_root / skill.rel_path
    source_hashes = compute_file_hashes(src)

    # phase 1: decide each provider's action without mutating anything
    decisions = _decide_actions(
        ctx.provider_registry, entry, skill_name, source_hashes=source_hashes
    )

    # before any copy, see whether it would detach and
    # try to re-pin it to a reachable commit whose content matches
    #
    # previously-skipped copies become UPDATE
    # the shared in_sync path below then advances the baseline and reports RECOVERED
    if not _decisions_in_sync(decisions) and _would_detach(entry, repo):
        reattached = _attempt_safe_reattach(
            decisions, repo=repo, rel_path=skill.rel_path
        )
        if reattached is not None:
            entry = InstalledSkill(
                source=entry.source,
                baseline=reattached,
                detached=True,
            )
            decisions = _decide_actions(
                ctx.provider_registry, entry, skill_name, source_hashes=source_hashes
            )

    # resolve the verified commit before any copy so a dirty/uncommitted source
    # aborts before touching install dirs; only needed when a copy will occur
    # (FRESH/UPDATE) or the baseline will advance (in_sync)
    needs_commit = any(d.action is not _Action.SKIPPED for d in decisions)
    latest_commit: str | None = None
    if needs_commit:
        latest_commit = resolve_verified_commit(repo, skill.rel_path)

    # phase 2: apply the copies now that the commit is verified
    provider_statuses = _apply_actions(decisions, src=src)

    # advance the baseline only when every provider is content-synced; the
    # empty registry is never content-synced, so the baseline stays put
    in_sync = bool(provider_statuses) and all(
        s in _SYNCED_STATES for s in provider_statuses.values()
    )

    if not in_sync:
        # skipped (locally modified): leave the baseline untouched,
        # only detect whether the recorded commit has fallen off the pinned branch
        reachable = entry.baseline is not None and repo.git.is_ancestor(
            entry.baseline.commit, repo.branch
        )

        if entry.baseline is not None and not reachable and not entry.detached:
            transition = _Detach.NEWLY_DETACHED
        elif entry.detached:
            transition = _Detach.STILL_DETACHED
        else:
            transition = _Detach.NONE

        return _SkillReport(
            provider_statuses=provider_statuses,
            baseline=entry.baseline,
            transition=transition,
        )

    # content-synced: advance the whole baseline to the verified latest commit
    # `in_sync` implies a verified commit was resolved
    if latest_commit is None:
        raise AssertionError("internal: content-synced skill without a resolved commit")

    # guard the baseline invariant: only content-synced copies may advance the
    # baseline; if a non-synced copy reaches this point (e.g. a loosened reattach
    # fingerprint guard) fail loudly instead of advancing over a local edit
    if not all(s in _SYNCED_STATES for s in provider_statuses.values()):
        raise AssertionError(
            "internal: content-synced skill advancing baseline over a non-synced copy"
        )

    baseline = Baseline(commit=latest_commit, files=source_hashes)
    transition = _Detach.RECOVERED if entry.detached else _Detach.NONE

    return _SkillReport(
        provider_statuses=provider_statuses,
        baseline=baseline,
        transition=transition,
    )


def _attempt_safe_reattach(
    decisions: list[_ProviderDecision],
    *,
    repo: SyncedRepo,
    rel_path: str,
) -> Baseline | None:
    # build the fingerprint from the pre-apply content of the installed copies only
    # a freshly-written copy must not influence the search
    # all such copies must be byte-identical, otherwise the fingerprint is ambiguous
    # and we must not silently re-pin a baseline
    fingerprint: dict[str, str] | None = None
    for decision in decisions:
        if decision.current_hashes is None:
            continue

        if fingerprint is None:
            fingerprint = decision.current_hashes
        elif decision.current_hashes != fingerprint:
            return None

    if fingerprint is None:
        return None

    found = find_commit_with_content(repo.git, rel_path, fingerprint)
    if found is None:
        return None

    return Baseline(commit=found, files=fingerprint)


def _decisions_in_sync(decisions: list[_ProviderDecision]) -> bool:
    # mirror the post-apply `in_sync` check using only the planned actions
    statuses = [_ACTION_STATUS[d.action] for d in decisions]
    return bool(statuses) and all(s in _SYNCED_STATES for s in statuses)


def _would_detach(entry: InstalledSkill, repo: SyncedRepo) -> bool:
    if entry.detached:
        return True

    if entry.baseline is None:
        return False

    return not repo.git.is_ancestor(entry.baseline.commit, repo.branch)


@dataclass(frozen=True)
class _ProviderDecision:
    name: str
    dst: Path
    action: _Action
    # pre-apply content of the install dir, or `None` when the dir was absent (FRESH)
    # the reattach fingerprint is built only from genuinely-installed copies,
    # never re-read after `_apply_actions` overwrites them
    current_hashes: dict[str, str] | None


def _decide_actions(
    provider_registry: ProviderRegistry,
    entry: InstalledSkill,
    skill_name: str,
    *,
    source_hashes: dict[str, str],
) -> list[_ProviderDecision]:
    decisions: list[_ProviderDecision] = []

    for provider in provider_registry.providers:
        dst = provider.install_path / skill_name
        if not dst.exists():
            decisions.append(_ProviderDecision(provider.name, dst, _Action.FRESH, None))
            continue

        current_hashes = compute_file_hashes(dst)
        if current_hashes == source_hashes:
            action = _Action.UP_TO_DATE
        elif entry.match_files(current_hashes):
            # in sync with what was installed, but outdated: overwrite
            action = _Action.UPDATE
        else:
            # installed skill was locally modified, don't touch it
            action = _Action.SKIPPED

        decisions.append(_ProviderDecision(provider.name, dst, action, current_hashes))

    return decisions


def _apply_actions(
    decisions: list[_ProviderDecision],
    *,
    src: Path,
) -> dict[str, _Status]:
    provider_statuses: dict[str, _Status] = {}

    for decision in decisions:
        if decision.action in (_Action.FRESH, _Action.UPDATE):
            overwrite_dir(src, decision.dst)

        provider_statuses[decision.name] = _ACTION_STATUS[decision.action]

    return provider_statuses


def _print_skill_report(report: _SkillReport) -> None:
    unique = set(report.provider_statuses.values())
    transition_label = _TRANSITION_LABEL.get(report.transition)

    if len(report.provider_statuses) > 1 and len(unique) > 1:
        if transition_label is not None:
            reporter.finish(transition_label)

        for prov_name, prov_status in report.provider_statuses.items():
            reporter.print(f"  {fmt_data(prov_name)}: {_STATUS_LABEL[prov_status]}")
        return

    if _Status.SKIPPED in unique and _Status.UPDATED not in unique:
        status = _STATUS_LABEL[_Status.SKIPPED]
    elif _Status.UPDATED in unique:
        status = _STATUS_LABEL[_Status.UPDATED]
    else:
        status = _STATUS_LABEL[_Status.UP_TO_DATE]

    if report.transition is _Detach.STILL_DETACHED:
        # untracked replaces the status line rather than annotating it
        status = _UNTRACKED
    elif transition_label is not None:
        status = f"{status}, {transition_label}"

    reporter.finish(status)
