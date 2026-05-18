from __future__ import annotations

import os
import shutil
import textwrap
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.text import Text
from typer_di import Depends, TyperDI

from repo_skills._git import GitRepo
from repo_skills.discovery import find_install_dir, find_repo_skills_dir
from repo_skills.manifest import Manifest, SkillEntry, default_manifest_path

app = TyperDI(
    help="Manage Claude Code skills.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


def resolve_repo_dir(
    repo_skills_dir: Annotated[
        Optional[str],
        typer.Option(
            "--repo-skills-dir",
            help="Path to the repo skills directory.",
            file_okay=False,
            dir_okay=True,
            exists=True,
        ),
    ] = None,
) -> Path:
    if repo_skills_dir:
        return Path(repo_skills_dir)

    repo_dir = find_repo_skills_dir()
    if repo_dir is None:
        typer.echo("Cannot find skills repo. Run from within the repo.", err=True)
        raise typer.Exit(1)

    return repo_dir


def resolve_install_dir_opt(
    install_dir: Annotated[
        Optional[str],
        typer.Option(
            "--install-dir",
            help="Path to the skill install directory.",
            file_okay=False,
            dir_okay=True,
            exists=True,
        ),
    ] = None,
) -> Optional[Path]:
    if install_dir:
        return Path(install_dir)
    return find_install_dir()


def resolve_install_dir(
    install_dir: Optional[Path] = Depends(resolve_install_dir_opt),
) -> Path:
    if install_dir is None:
        typer.echo("Cannot find install directory.", err=True)
        raise typer.Exit(1)

    return install_dir


def resolve_manifest_path(
    manifest_path: Annotated[
        Optional[str],
        typer.Option("--manifest-path", help="Path to the manifest file."),
    ] = None,
) -> Path:
    if manifest_path:
        return Path(manifest_path)
    return default_manifest_path()


class UpdateStatus(Enum):
    UPDATED = "updated"
    UP_TO_DATE = "up-to-date"
    CONFLICT = "conflict"
    ERROR = "error"


_git_repo_factory: Callable[[Path], GitRepo] | None = None


def resolve_git_repo(repo_dir: Path) -> GitRepo:
    if _git_repo_factory is not None:
        return _git_repo_factory(repo_dir)
    from repo_skills._git_real import RealGitRepo

    return RealGitRepo(repo_dir)


@app.command(help="Install a skill from the repo.")
def install(
    *,
    name: str,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip git pull."),
    ] = False,
    repo_dir: Path = Depends(resolve_repo_dir),
    install_dir: Optional[Path] = Depends(resolve_install_dir_opt),
    manifest_path: Path = Depends(resolve_manifest_path),
) -> None:
    git = resolve_git_repo(repo_dir.parent)

    if not offline:
        git.pull()

    _validate_repo(git)

    src = repo_dir / name
    if not src.is_dir():
        typer.echo(f"Skill '{name}' not found in repo.", err=True)
        raise typer.Exit(1)

    if install_dir is None:
        install_dir = manifest_path.parent
    install_dir.mkdir(parents=True, exist_ok=True)

    dst = install_dir / name
    if dst.exists():
        typer.echo(f"Skill '{name}' is already installed.", err=True)
        raise typer.Exit(1)

    commit = _resolve_commit(git, name)

    shutil.copytree(src, dst)

    manifest = Manifest.load(manifest_path)
    manifest.repo_path = str(repo_dir.parent)
    manifest.skills[name] = SkillEntry(commit=commit)
    manifest.save(manifest_path)

    typer.echo(f"Installed '{name}'.")


def _validate_repo(git: GitRepo) -> None:
    main = git.get_main_branch()
    current = git.current_branch()
    if current != main:
        typer.echo(
            f"Not on main branch (on '{current}', expected '{main}').",
            err=True,
        )
        raise typer.Exit(1)

    if not git.is_clean():
        typer.echo("Repo has uncommitted changes.", err=True)
        raise typer.Exit(1)


def _resolve_commit(git: GitRepo, skill_name: str) -> str:
    commit = git.get_skill_commit(skill_name)
    if not git.verify_commit_content(commit, skill_name):
        typer.echo(
            f"Skill '{skill_name}' content does not match commit {commit}.",
            err=True,
        )
        raise typer.Exit(1)
    return commit


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


@app.command(help="Show changes between repo and installed skills.")
def peek() -> None:
    pass


@app.command(help="Resolve conflicts between repo and installed skills.")
def merge() -> None:
    pass


@app.command(name="list", help="List available and installed skills.")
def list_(
    repo_dir: Path = Depends(resolve_repo_dir),
    install_dir: Path = Depends(resolve_install_dir),
) -> None:
    repo_skills = {d.name for d in repo_dir.iterdir() if d.is_dir()}
    installed = {
        d.name
        for d in install_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    }

    groups: list[tuple[str, str, list[str]]] = [
        ("Installed", "green", sorted(repo_skills & installed)),
        ("Not in repo", "yellow", sorted(installed - repo_skills)),
        ("Not installed", "dim", sorted(repo_skills - installed)),
    ]

    all_names = [n for _, _, names in groups for n in names]
    col_width = max((len(n) for n in all_names), default=0)
    prefix_len = 2 + col_width + 1

    console = Console(highlight=False)
    first = True
    for header, style, names in groups:
        if not names:
            continue

        if not first:
            console.print()
        first = False

        console.print(f"[{style}]{header}[/{style}]")
        for name in names:
            desc = _read_skill_description(
                name, install_dir if name in installed else repo_dir
            )
            padded = f"{name:<{col_width}}"
            if not desc:
                console.print(
                    f"[dim cyan]*[/dim cyan] [bright_white]{padded}[/bright_white]"
                )
                continue

            desc_width = max(console.width - prefix_len, 20)
            lines = textwrap.wrap(desc, width=desc_width)
            indent = " " * prefix_len
            wrapped = f"\n{indent}".join(lines)
            text = Text.from_markup(
                f"[dim cyan]*[/dim cyan] [bright_white]{padded}[/bright_white] "
                f"[dim]{wrapped}[/dim]"
            )
            console.print(text, soft_wrap=True)


def _read_skill_description(name: str, base_dir: Path) -> str:
    skill_md = base_dir / name / "SKILL.md"
    if not skill_md.exists():
        return ""

    content = skill_md.read_text()

    if not content.startswith("---"):
        return ""

    end = content.find("---", 3)
    if end == -1:
        return ""

    for line in content[3:end].splitlines():
        if line.startswith("description:"):
            return line[len("description:") :].strip()

    return ""


@app.command(help="Uninstall a skill.")
def uninstall(
    name: str,
    install_dir: Path = Depends(resolve_install_dir),
    manifest_path: Path = Depends(resolve_manifest_path),
) -> None:
    dst = install_dir / name
    if not dst.exists():
        typer.echo(f"Skill '{name}' is not installed.", err=True)
        raise typer.Exit(1)

    shutil.rmtree(dst)

    manifest = Manifest.load(manifest_path)
    manifest.skills.pop(name, None)
    manifest.save(manifest_path)

    typer.echo(f"Uninstalled '{name}'.")
