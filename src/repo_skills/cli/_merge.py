from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

from repo_skills.config import (
    ProviderRegistry,
    SkillEntry,
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_config,
    load_source_registry,
    save_skill_manifest,
)
from repo_skills.errors import AppError
from repo_skills.git import GitRepo

from ._app import app
from ._deps import resolve_git_repo
from ._utils import echo

MERGE_BRANCH_PREFIX = "skill-merge/"


@app.command(help="Merge provider edits back into a source repo.")
def merge(
    *,
    name: Annotated[
        Optional[str],
        typer.Argument(help="Skill to merge."),
    ] = None,
    from_provider: Annotated[
        Optional[str],
        typer.Option(
            "--from", help="Provider to merge from (required when ambiguous)."
        ),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip git pull."),
    ] = False,
    continue_merge: Annotated[
        bool,
        typer.Option("--continue", help="Finalize a merge in progress."),
    ] = False,
) -> None:
    if continue_merge:
        _merge_continue()
        return

    if name is None:
        raise AppError("Skill name is required (or use [blue]--continue[/blue]).")

    _merge_start(name, from_provider=from_provider, offline=offline)


def _merge_start(
    name: str,
    *,
    from_provider: str | None,
    offline: bool,
) -> None:
    manifest = load_skill_manifest()
    if name not in manifest.skills:
        raise AppError(f"Skill [cyan]{name}[/cyan] is not installed.")

    entry = manifest.skills[name]
    if entry.commit is None:
        raise AppError(
            f"Skill [cyan]{name}[/cyan] has no base commit.\n"
            f"Run [blue]skills update[/blue] first."
        )

    source_name = entry.source
    registry = load_source_registry()
    if source_name not in registry.sources:
        raise AppError(f"Source [cyan]{source_name}[/cyan] not found.")

    source_path = Path(registry.sources[source_name].path)
    git = resolve_git_repo(source_path)

    existing = git.list_branches(f"{MERGE_BRANCH_PREFIX}*")
    if existing:
        names = ", ".join(
            f"[green]{p.removeprefix(MERGE_BRANCH_PREFIX)}[/green]"
            for p in sorted(existing)
        )
        raise AppError(
            f"Merge already in progress: {names}.\n\n"
            "Run [blue]skills merge --continue[/blue] to finish active merge "
            "or [blue]skills merge --abort[/blue] to start over."
        )

    if not git.is_clean():
        raise AppError(
            f"Repo has uncommitted changes.\n  repo: [cyan]{git.path}[/cyan]"
        )

    main_branch = git.get_main_branch()
    if git.current_branch() != main_branch:
        git.checkout(main_branch)

    if not offline:
        git.pull()

    providers = load_provider_registry()
    provider_name = _resolve_provider(name, entry, providers, from_provider)

    provider_install_dir = Path(
        providers.providers[provider_name].install_dir
    ).expanduser()
    installed_path = provider_install_dir / name

    source_cfg = load_source_config(source_path)
    skill_src = source_path / source_cfg.skills_dir / name

    branch_name = f"skill-merge/{provider_name}/{name}"
    git.create_branch(branch_name, entry.commit)

    _copy_provider_to_source(installed_path, skill_src)

    git.commit_all(f"chore: merge {name} from {provider_name}")

    clean = git.rebase(main_branch)
    if clean:
        echo("[green]✨ Rebase clean![/green]\n")
        echo("Run [blue]skills merge --continue[/blue] to finalize.")
        return

    echo("[yellow]⚠️ Rebase has conflicts.[/yellow]\n")
    echo("Resolve them, then run [blue]skills merge --continue[/blue].")


def _merge_continue() -> None:
    git = _detect_merge_repo()
    branch = _detect_merge_branch(git)
    provider_name, skill_name = _parse_merge_branch(branch)

    rebasing = git.is_rebasing()
    if rebasing:
        git.rebase_continue()
    elif not git.is_clean():
        raise AppError(
            f"Repo has uncommitted changes.\n  repo: [cyan]{git.path}[/cyan]"
        )

    manifest = load_skill_manifest()
    entry = manifest.skills[skill_name]

    source_name = entry.source
    registry = load_source_registry()
    source_path = Path(registry.sources[source_name].path)
    source_cfg = load_source_config(source_path)
    skill_src = source_path / source_cfg.skills_dir / skill_name

    main_branch = git.get_main_branch()
    git.checkout(main_branch)
    git.fast_forward(branch)

    providers = load_provider_registry()
    provider_install_dir = Path(
        providers.providers[provider_name].install_dir
    ).expanduser()
    installed_path = provider_install_dir / skill_name

    _copy_provider_to_source(skill_src, installed_path)

    new_hashes = compute_file_hashes(installed_path)
    empty = new_hashes == entry.files

    entry.commit = git.get_skill_commit(skill_name)
    entry.files = new_hashes
    save_skill_manifest(manifest)

    git.delete_branch(branch)

    if empty:
        echo(
            f"👌 Nothing to merge for [cyan]{skill_name}[/cyan] "
            "— [bold]already up to date[/bold]."
        )
        return

    echo(f"[green]👍 Merge complete for [cyan]{skill_name}[/cyan].[/green]")


def _detect_merge_repo() -> "GitRepo":
    manifest = load_skill_manifest()
    for entry in manifest.skills.values():
        source_name = entry.source
        registry = load_source_registry()
        if source_name in registry.sources:
            source_path = Path(registry.sources[source_name].path)
            return resolve_git_repo(source_path)
    raise AppError("No source repo found.")


def _detect_merge_branch(git: "GitRepo") -> str:
    current = git.current_branch()
    if current.startswith(MERGE_BRANCH_PREFIX):
        return current

    branches = git.list_branches(f"{MERGE_BRANCH_PREFIX}*")
    if len(branches) == 1:
        return branches[0]

    if len(branches) > 1:
        names = ", ".join(sorted(branches))
        raise AppError(
            f"Multiple merge branches found ({names}).\n"
            f"Checkout the one to continue."
        )

    raise AppError("No merge branch found. Run [blue]skills merge[/blue] first.")


def _parse_merge_branch(branch: str) -> tuple[str, str]:
    parts = branch.removeprefix(MERGE_BRANCH_PREFIX).split("/", 1)
    if len(parts) != 2:
        raise AppError(f"Invalid merge branch: [cyan]{branch}[/cyan]")
    return parts[0], parts[1]


def _resolve_provider(
    skill_name: str,
    entry: SkillEntry,
    providers: ProviderRegistry,
    from_provider: str | None,
) -> str:
    if from_provider is not None:
        if from_provider not in providers.providers:
            raise AppError(f"Provider [cyan]{from_provider}[/cyan] not found.")
        return from_provider

    diverged: list[str] = []
    for pname, pcfg in providers.providers.items():
        install_dir = Path(pcfg.install_dir).expanduser()
        installed_path = install_dir / skill_name
        if not installed_path.exists():
            continue

        current_hashes = compute_file_hashes(installed_path)
        if current_hashes != entry.files:
            diverged.append(pname)

    if not diverged:
        raise AppError(
            f"No provider has modified [cyan]{skill_name}[/cyan]. Nothing to merge."
        )

    if len(diverged) > 1:
        names = ", ".join(sorted(diverged))
        raise AppError(
            f"Multiple providers have modified [cyan]{skill_name}[/cyan] ({names}).\n"
            f"Use [blue]--from[/blue] to specify."
        )

    return diverged[0]


def _copy_provider_to_source(installed_path: Path, skill_src: Path) -> None:
    if skill_src.exists():
        shutil.rmtree(skill_src)
    shutil.copytree(installed_path, skill_src)
