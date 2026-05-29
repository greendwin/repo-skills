from __future__ import annotations

import shutil
from typing import Annotated, Optional

import typer

from repo_skills.config import (
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
    save_skill_manifest,
)
from repo_skills.errors import AppError, NoopError
from repo_skills.utils import fmt_ident

from ._app import app
from ._deps import resolve_git_repo
from ._utils import echo, ensure_on_branch

_UPDATED = "[green]updated[/green]"
_SKIPPED = "[yellow]skipped (modified)[/yellow]"
_UP_TO_DATE = "[dim]up to date[/dim]"
_DETACHED = "[yellow]detached (commit unreachable)[/yellow]"
_RECOVERED = "[green]recovered[/green]"


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

    if not manifest.skills:
        raise NoopError("[dim]No skills installed.[/dim]")

    if name and name not in manifest.skills:
        raise AppError(f"Skill {fmt_ident(name)} is not installed.")

    source_branches: dict[str, str] = {}
    for source_name in source_registry.sources:
        source = source_registry.get_source(source_name, load_skills=False)
        git = resolve_git_repo(source.repo_root)
        branch = source.get_branch(git)

        echo(f"Pulling {source_name} … ", end="")
        ensure_on_branch(git, branch, pull=not offline)
        source_branches[source_name] = branch
        if offline:
            echo("[dim]skipped[/dim]")
        else:
            echo("[green]done[/green]")

    skills_to_update = {name: manifest.skills[name]} if name else dict(manifest.skills)

    for skill_name, entry in skills_to_update.items():
        echo(f"Updating {skill_name} … ", end="")

        if entry.source not in source_registry.sources:
            echo(f"[red]error: source '{entry.source}' not found[/red]")
            continue

        source = source_registry.get_source(entry.source, load_skills=True)
        skill = source.skills.get(skill_name)

        if skill is None:
            echo("[red]error: skill removed from source[/red]")
            continue

        src = source.repo_root / skill.rel_path

        source_hashes = compute_file_hashes(src)
        updated_any = False
        skipped_any = False

        for provider in providers.providers:
            install_dir = provider.install_path
            dst = install_dir / skill_name

            if not dst.exists():
                install_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst)
                updated_any = True
                continue

            current_hashes = compute_file_hashes(dst)

            if current_hashes == source_hashes:
                continue

            if current_hashes != entry.files:
                skipped_any = True
                continue

            shutil.rmtree(dst)
            shutil.copytree(src, dst)
            updated_any = True

        if skipped_any and not updated_any:
            status = _SKIPPED
        elif updated_any:
            status = _UPDATED
        else:
            status = _UP_TO_DATE

        detached = entry.detached
        if entry.commit and entry.source in source_branches:
            git = resolve_git_repo(source.repo_root)
            pinned = source_branches[entry.source]
            reachable = git.is_ancestor(entry.commit, pinned)
            if reachable and entry.detached:
                detached = False
                status = f"{status}, {_RECOVERED}"
            elif not reachable and not entry.detached:
                detached = True
                status = f"{status}, {_DETACHED}"

        echo(status)

        manifest.register_skill(
            skill_name,
            source_name=entry.source,
            commit=entry.commit,
            files=source_hashes,
            detached=detached,
        )

    save_skill_manifest(manifest)
