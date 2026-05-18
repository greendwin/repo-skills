from __future__ import annotations

import os
import shutil
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from typer_di import Depends

from repo_skills.manifest import Manifest, SkillEntry

from ._app import app
from ._deps import (
    resolve_git_repo,
    resolve_install_dir,
    resolve_manifest_path,
    resolve_repo_dir,
)
from ._install import _validate_repo


class UpdateStatus(Enum):
    UPDATED = "updated"
    UP_TO_DATE = "up-to-date"
    CONFLICT = "conflict"
    ERROR = "error"


@app.command(help="Update installed skills from the repo.")
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
    repo_dir: Path = Depends(resolve_repo_dir),
    install_dir: Path = Depends(resolve_install_dir),
    manifest_path: Path = Depends(resolve_manifest_path),
) -> None:
    git = resolve_git_repo(repo_dir.parent)

    if not offline:
        git.pull()

    _validate_repo(git)

    manifest = Manifest.load(manifest_path)

    names = _collect_skills(
        selected_skill=name, manifest=manifest, install_dir=install_dir
    )

    results: list[tuple[str, UpdateStatus]] = []

    for skill_name in names:
        dst = install_dir / skill_name
        if skill_name not in manifest.skills and not dst.exists():
            typer.echo(f"Skill '{skill_name}' is not installed.", err=True)
            raise typer.Exit(1)

        src = repo_dir / skill_name

        if not src.is_dir():
            typer.echo(f"Skill '{skill_name}' not found in repo.", err=True)
            raise typer.Exit(1)

        commit = git.get_skill_commit(skill_name)
        if not git.verify_commit_content(commit, skill_name):
            results.append((skill_name, UpdateStatus.ERROR))
            continue

        entry = manifest.skills.get(skill_name, SkillEntry())
        if entry.commit == commit:
            results.append((skill_name, UpdateStatus.UP_TO_DATE))
            continue

        if dst.exists() and not _has_conflict(src, dst):
            manifest.skills[skill_name] = SkillEntry(commit=commit)
            results.append((skill_name, UpdateStatus.UP_TO_DATE))
            continue

        if dst.exists() and _has_conflict(src, dst):
            results.append((skill_name, UpdateStatus.CONFLICT))
            continue

        shutil.copytree(src, dst)

        manifest.skills[skill_name] = SkillEntry(commit=commit)
        results.append((skill_name, UpdateStatus.UPDATED))

    manifest.save(manifest_path)
    _print_report(results)


def _collect_skills(
    *, install_dir: Path, selected_skill: str | None, manifest: Manifest
) -> list[str]:
    if selected_skill:
        return [selected_skill]

    on_disk = set()

    if install_dir.exists():
        on_disk = {
            d.name
            for d in install_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        }

    return sorted(on_disk | set(manifest.skills.keys()))


_STATUS_LABELS = {
    UpdateStatus.UPDATED: "Updated",
    UpdateStatus.UP_TO_DATE: "Up to date",
    UpdateStatus.CONFLICT: "Skipped",
    UpdateStatus.ERROR: "Skipped",
}

_STATUS_DETAIL = {
    UpdateStatus.CONFLICT: "conflict: local changes",
    UpdateStatus.ERROR: "error: commit content mismatch",
}


def _print_report(results: list[tuple[str, UpdateStatus]]) -> None:
    for skill_name, status in results:
        label = _STATUS_LABELS[status]
        detail = _STATUS_DETAIL.get(status)
        if detail:
            typer.echo(f"  {label} '{skill_name}': {detail}")
        else:
            typer.echo(f"  {label} '{skill_name}'")

    counts = {s: sum(1 for _, st in results if st == s) for s in UpdateStatus}

    parts = []
    if counts[UpdateStatus.UPDATED]:
        parts.append(f"{counts[UpdateStatus.UPDATED]} updated")
    if counts[UpdateStatus.UP_TO_DATE]:
        parts.append(f"{counts[UpdateStatus.UP_TO_DATE]} up to date")
    if counts[UpdateStatus.CONFLICT]:
        parts.append(f"{counts[UpdateStatus.CONFLICT]} conflict")
    if counts[UpdateStatus.ERROR]:
        parts.append(f"{counts[UpdateStatus.ERROR]} error")

    if parts:
        typer.echo(", ".join(parts))


def _has_conflict(src: Path, dst: Path) -> bool:
    src_files = _collect_files(src)
    dst_files = _collect_files(dst)

    if set(src_files.keys()) != set(dst_files.keys()):
        return True

    for rel_path, src_content in src_files.items():
        if dst_files[rel_path] != src_content:
            return True

    return False


def _collect_files(root: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            full = Path(dirpath) / fname
            rel = str(full.relative_to(root))
            with full.open("rb") as f:
                result[rel] = f.read()
    return result
