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
)
from repo_skills.errors import AppError

from ._app import app
from ._deps import resolve_git_repo
from ._utils import echo


@app.command(help="Merge provider edits back into a source repo.")
def merge(
    *,
    name: str,
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
) -> None:
    manifest = load_skill_manifest()
    if name not in manifest.skills:
        raise AppError(f"Skill [cyan]{name}[/cyan] is not installed.")

    entry = manifest.skills[name]
    if entry.commit is None:
        raise AppError(
            f"Skill [cyan]{name}[/cyan] has no base commit.\n"
            f"Run [bold]skills update[/bold] first."
        )

    source_name = entry.source
    registry = load_source_registry()
    if source_name not in registry.sources:
        raise AppError(f"Source [cyan]{source_name}[/cyan] not found.")

    source_path = Path(registry.sources[source_name].path)
    git = resolve_git_repo(source_path)

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
        echo("Rebase clean. Run [bold]skills merge --continue[/bold] to finalize.")
    else:
        echo(
            "Rebase has conflicts. Resolve them, then run "
            "[bold]skills merge --continue[/bold]."
        )


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
            f"Use [bold]--from[/bold] to specify."
        )

    return diverged[0]


def _copy_provider_to_source(installed_path: Path, skill_src: Path) -> None:
    if skill_src.exists():
        shutil.rmtree(skill_src)
    shutil.copytree(installed_path, skill_src)
