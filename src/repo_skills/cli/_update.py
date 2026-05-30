from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum, auto
from typing import Annotated, Optional

import typer
from rich.markup import escape

from repo_skills.config import (
    InstalledSkill,
    ProviderRegistry,
    SourceRegistry,
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
    save_skill_manifest,
)
from repo_skills.console import console, fmt_data, fmt_ident
from repo_skills.errors import AppError, NoopError

from ._app import app
from ._deps import resolve_git_repo
from ._utils import ensure_on_branch


class _Status(Enum):
    UPDATED = auto()
    SKIPPED = auto()
    UP_TO_DATE = auto()


_STATUS_LABEL: dict[_Status, str] = {
    _Status.UPDATED: "[green]updated[/green]",
    _Status.SKIPPED: "[yellow]skipped (modified)[/yellow]",
    _Status.UP_TO_DATE: "[dim]up to date[/dim]",
}
_DETACHED = "[yellow]detached (commit unreachable)[/yellow]"
_RECOVERED = "[green]recovered[/green]"


class _SkillError(Exception):
    pass


@dataclass
class _SkillReport:
    provider_statuses: dict[str, _Status]
    source_hashes: dict[str, str]
    detached: bool
    recovered: bool = False
    newly_detached: bool = False


def _update_skill(
    skill_name: str,
    entry: InstalledSkill,
    source_registry: SourceRegistry,
    providers: ProviderRegistry,
    source_branches: dict[str, str],
) -> _SkillReport:
    if entry.source not in source_registry.sources:
        raise _SkillError(f"source '{entry.source}' not found")

    source = source_registry.get_source(entry.source, load_skills=True)
    skill = source.skills.get(skill_name)

    if skill is None:
        raise _SkillError("skill removed from source")

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

        if current_hashes != entry.files:
            provider_statuses[provider.name] = _Status.SKIPPED
            continue

        shutil.rmtree(dst)
        shutil.copytree(src, dst)
        provider_statuses[provider.name] = _Status.UPDATED

    detached = entry.detached
    recovered = False
    newly_detached = False

    if entry.commit and entry.source in source_branches:
        git = resolve_git_repo(source.repo_root)
        pinned = source_branches[entry.source]
        reachable = git.is_ancestor(entry.commit, pinned)
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


@app.command(help="Update installed skills from sources.")
def update(
    *,
    name: Annotated[
        Optional[str],
        typer.Argument(help="Skill to update (all if omitted)."),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip git pull."),
    ] = False,
) -> None:
    source_registry = load_source_registry()
    providers = load_provider_registry()
    manifest = load_skill_manifest()

    # TODO: can we do anything with skills that are not in manifest?
    if not manifest.skills:
        raise NoopError("[dim]No skills installed.[/dim]")

    if name and name not in manifest.skills:
        raise AppError(f"Skill {fmt_ident(name)} is not installed.")

    source_branches: dict[str, str] = {}
    for source_name in source_registry.sources:
        source = source_registry.get_source(source_name, load_skills=False)
        git = resolve_git_repo(source.repo_root)
        branch = source.get_branch(git)

        with console.running(f"Pulling {fmt_data(source_name)}"):
            ensure_on_branch(git, branch, pull=not offline)
            source_branches[source_name] = branch
            if offline:
                console.print("[dim]skipped[/dim]")
            else:
                console.print("[green]done[/green]")

    skills_to_update = {name: manifest.skills[name]} if name else dict(manifest.skills)

    for skill_name, entry in skills_to_update.items():
        with console.running(f"Updating {fmt_data(skill_name)}"):
            try:
                report = _update_skill(
                    skill_name, entry, source_registry, providers, source_branches
                )
            except _SkillError as ex:
                console.print(f"[red]error: {escape(str(ex))}[/red]")
                continue
            except Exception as ex:
                console.print(f"[red]error: {escape(str(ex))}[/red]")
                if console.debug:
                    console.print_exception()
                continue

            _print_skill_report(skill_name, report)

            manifest.register_skill(
                skill_name,
                source_name=entry.source,
                commit=entry.commit,
                files=report.source_hashes,
                detached=report.detached,
            )

    save_skill_manifest(manifest)


def _print_skill_report(skill_name: str, report: _SkillReport) -> None:
    unique = set(report.provider_statuses.values())

    if len(report.provider_statuses) > 1 and len(unique) > 1:
        if report.recovered:
            console.finish(_RECOVERED)
        elif report.newly_detached:
            console.finish(_DETACHED)

        # we should print several distinct statuses for same skill based on provider
        for prov_name, pstatus in report.provider_statuses.items():
            console.print(f"  {fmt_data(prov_name)}: {_STATUS_LABEL[pstatus]}")
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

    console.finish(status)
