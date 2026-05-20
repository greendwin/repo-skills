from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from repo_skills.config import (
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
)

from ._app import app
from ._deps import resolve_git_repo
from ._utils import echo


@app.command(help="Show status of installed skills.")
def status(
    *,
    sync: Annotated[
        bool,
        typer.Option("--sync", help="Pull source repos before checking."),
    ] = False,
) -> None:
    manifest = load_skill_manifest()

    if not manifest.skills:
        echo("[dim]No skills installed.[/dim]")
        return

    sources = load_source_registry()

    if sync:
        for sentry in sources.sources.values():
            git = resolve_git_repo(Path(sentry.path))
            git.pull()

    providers = load_provider_registry()

    by_source: dict[str, list[str]] = {}
    for skill_name, entry in manifest.skills.items():
        by_source.setdefault(entry.source, []).append(skill_name)

    for source_name, skill_names in sorted(by_source.items()):
        echo(f"[yellow]{source_name}[/yellow]")

        for skill_name in sorted(skill_names):
            entry = manifest.skills[skill_name]

            for pname, pcfg in providers.providers.items():
                install_dir = Path(pcfg.install_dir).expanduser()
                installed_path = install_dir / skill_name
                divergence = _check_divergence(installed_path, entry.files)
                echo(f"  {skill_name}  [dim]{pname}[/dim] {divergence}")


def _check_divergence(installed_path: Path, baseline: dict[str, str]) -> str:
    if not installed_path.exists():
        return "[red]missing[/red]"

    current = compute_file_hashes(installed_path)
    if current == baseline:
        return "[green]synced[/green]"

    return "[yellow]modified[/yellow]"
