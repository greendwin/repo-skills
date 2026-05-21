from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

from repo_skills.config import (
    SkillEntry,
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_config,
    load_source_registry,
    save_skill_manifest,
)
from repo_skills.errors import AppError, NoopError

from ._app import app
from ._deps import resolve_git_repo
from ._install import _validate_repo
from ._utils import echo


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
    any_branch: Annotated[
        bool,
        typer.Option("--any-branch", help="Allow update from any branch."),
    ] = False,
) -> None:
    sources = load_source_registry()
    providers = load_provider_registry()
    manifest = load_skill_manifest()

    if not manifest.skills:
        raise NoopError("[dim]No skills installed.[/dim]")

    if name and name not in manifest.skills:
        raise AppError(f"Skill [green]{name}[/green] is not installed.")

    for sentry in sources.sources.values():
        source_path = Path(sentry.path)
        git = resolve_git_repo(source_path)
        if not offline:
            git.pull()
        _validate_repo(git, any_branch=any_branch)

    skills_to_update = {name: manifest.skills[name]} if name else dict(manifest.skills)

    results: list[tuple[str, str]] = []

    for skill_name, entry in skills_to_update.items():
        source_entry = sources.sources.get(entry.source)
        if source_entry is None:
            results.append((skill_name, "error"))
            continue

        source_path = Path(source_entry.path)
        source_cfg = load_source_config(source_path)
        src = source_path / source_cfg.skills_dir / skill_name

        if not src.is_dir():
            results.append((skill_name, "error"))
            continue

        source_hashes = compute_file_hashes(src)
        updated_any = False
        skipped_any = False

        for _pname, pcfg in providers.providers.items():
            install_dir = Path(pcfg.install_dir).expanduser()
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
            results.append((skill_name, "skipped"))
        elif updated_any:
            results.append((skill_name, "updated"))
        else:
            results.append((skill_name, "up-to-date"))

        manifest.skills[skill_name] = SkillEntry(
            source=entry.source,
            commit=entry.commit,
            files=source_hashes,
        )

    save_skill_manifest(manifest)
    _print_report(results)


def _print_report(results: list[tuple[str, str]]) -> None:
    if not results:
        return

    _STATUS_LABELS = {
        "updated": "[green]updated[/green]",
        "skipped": "[yellow]skipped (modified)[/yellow]",
        "error": "[red]error[/red]",
        "up-to-date": "[dim]up to date[/dim]",
    }

    name_width = max(len(name) for name, _ in results)

    echo("[yellow]Update[/yellow]")
    for skill_name, status in results:
        label = _STATUS_LABELS.get(status, status)
        echo(f"  {skill_name:<{name_width}}  {label}")
