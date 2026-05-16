from __future__ import annotations

import os
import shutil
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.text import Text
from typer_di import Depends, TyperDI

from skill_cli._git import GitRepo
from skill_cli.discovery import find_install_dir, find_repo_skills_dir
from skill_cli.manifest import Manifest, SkillEntry, default_manifest_path

app = TyperDI(
    help="Manage Claude Code skills.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


def _copytree(src: Path, dst: Path) -> None:
    os.makedirs(str(dst), exist_ok=True)
    for item in os.listdir(str(src)):
        s = os.path.join(str(src), item)
        d = os.path.join(str(dst), item)
        if os.path.isdir(s):
            _copytree(Path(s), Path(d))
        else:
            with open(s, "rb") as f_in, open(d, "wb") as f_out:
                f_out.write(f_in.read())


def resolve_repo_dir(
    repo_skills_dir: Annotated[
        Optional[str],
        typer.Option("--repo-skills-dir", help="Path to the repo skills directory."),
    ] = None,
) -> Optional[Path]:
    if repo_skills_dir:
        return Path(repo_skills_dir)
    return find_repo_skills_dir()


def resolve_install_dir(
    install_dir: Annotated[
        Optional[str],
        typer.Option("--install-dir", help="Path to the skill install directory."),
    ] = None,
) -> Optional[Path]:
    if install_dir:
        return Path(install_dir)
    return find_install_dir()


def resolve_manifest_path(
    manifest_path: Annotated[
        Optional[str],
        typer.Option("--manifest-path", help="Path to the manifest file."),
    ] = None,
) -> Path:
    if manifest_path:
        return Path(manifest_path)
    return default_manifest_path()


_git_repo_factory: Callable[[Path], GitRepo] | None = None


def resolve_git_repo(repo_dir: Path) -> GitRepo:
    if _git_repo_factory is not None:
        return _git_repo_factory(repo_dir)
    from skill_cli._git_real import RealGitRepo

    return RealGitRepo(repo_dir)


def _require_repo_dir(repo_dir: Optional[Path]) -> Path:
    if repo_dir is None:
        typer.echo("Cannot find skills repo. Run from within the repo.", err=True)
        raise typer.Exit(1)
    return repo_dir


def _require_install_dir(inst_dir: Optional[Path]) -> Path:
    if inst_dir is None:
        typer.echo("Cannot find install directory.", err=True)
        raise typer.Exit(1)
    return inst_dir


@app.command(help="Install a skill from the repo.")
def install(
    *,
    name: str,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip git pull."),
    ] = False,
    repo_dir: Optional[Path] = Depends(resolve_repo_dir),
    install_dir: Optional[Path] = Depends(resolve_install_dir),
    manifest_path: Path = Depends(resolve_manifest_path),
) -> None:
    repo = _require_repo_dir(repo_dir)
    git = resolve_git_repo(repo.parent)

    if not offline:
        git.pull()

    _validate_repo(git)

    src = repo / name
    if not src.is_dir():
        typer.echo(f"Skill '{name}' not found in repo.", err=True)
        raise typer.Exit(1)

    if install_dir is None:
        install_dir = manifest_path.parent
    os.makedirs(str(install_dir), exist_ok=True)

    dst = install_dir / name
    if dst.exists():
        typer.echo(f"Skill '{name}' is already installed.", err=True)
        raise typer.Exit(1)

    commit = _resolve_commit(git, name)

    _copytree(src, dst)

    manifest = Manifest.load(manifest_path)
    manifest.repo_path = str(repo.parent)
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
    commit: Annotated[
        Optional[str],
        typer.Option("--commit", help="New commit hash to record in manifest."),
    ] = None,
    repo_dir: Optional[Path] = Depends(resolve_repo_dir),
    install_dir: Optional[Path] = Depends(resolve_install_dir),
    manifest_path: Path = Depends(resolve_manifest_path),
) -> None:
    repo = _require_repo_dir(repo_dir)
    inst = _require_install_dir(install_dir)
    manifest = Manifest.load(manifest_path)

    if name:
        names = [name]
    else:
        on_disk = (
            {
                d.name
                for d in inst.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            }
            if inst.exists()
            else set()
        )
        names = sorted(on_disk | set(manifest.skills.keys()))

    for skill_name in names:
        dst = inst / skill_name
        if skill_name not in manifest.skills and not dst.exists():
            typer.echo(f"Skill '{skill_name}' is not installed.", err=True)
            raise typer.Exit(1)

        entry = manifest.skills.get(skill_name, SkillEntry())
        if commit and entry.commit == commit:
            typer.echo(f"'{skill_name}' is already up to date.")
            continue

        src = repo / skill_name

        if not src.is_dir():
            typer.echo(f"Skill '{skill_name}' not found in repo.", err=True)
            raise typer.Exit(1)

        if dst.exists() and _has_conflict(src, dst):
            typer.echo(
                f"Conflict in '{skill_name}': both repo and local have"
                " changes.\n"
                "Use 'skill peek --diff' to view differences"
                " or 'skill merge' to resolve.",
                err=True,
            )
            raise typer.Exit(1)

        if dst.exists():
            shutil.rmtree(str(dst))
        _copytree(src, dst)

        manifest.skills[skill_name] = SkillEntry(commit=commit or "")
        typer.echo(f"Updated '{skill_name}'.")

    manifest.save(manifest_path)


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
    for dirpath, _, filenames in os.walk(str(root)):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, str(root))
            with open(full, "rb") as f:
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
    repo_dir: Optional[Path] = Depends(resolve_repo_dir),
    install_dir: Optional[Path] = Depends(resolve_install_dir),
) -> None:
    repo = _require_repo_dir(repo_dir)
    dest = _require_install_dir(install_dir)

    repo_skills = {d.name for d in repo.iterdir() if d.is_dir()}
    installed = {
        d.name for d in dest.iterdir() if d.is_dir() and not d.name.startswith(".")
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
            desc = _read_skill_description(name, dest if name in installed else repo)
            padded = f"{name:<{col_width}}"
            if desc:
                desc_width = max(console.width - prefix_len, 20)
                lines = textwrap.wrap(desc, width=desc_width)
                indent = " " * prefix_len
                wrapped = f"\n{indent}".join(lines)
                text = Text.from_markup(
                    f"[dim cyan]*[/dim cyan] [bright_white]{padded}[/bright_white] "
                    f"[dim]{wrapped}[/dim]"
                )
                console.print(text, soft_wrap=True)
            else:
                console.print(
                    f"[dim cyan]*[/dim cyan] [bright_white]{padded}[/bright_white]"
                )


def _read_skill_description(name: str, base_dir: Path) -> str:
    skill_md = base_dir / name / "SKILL.md"
    if not os.path.exists(str(skill_md)):
        return ""
    with open(str(skill_md)) as f:
        content = f.read()
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
    inst_dir: Optional[Path] = Depends(resolve_install_dir),
    mpath: Path = Depends(resolve_manifest_path),
) -> None:
    dest = _require_install_dir(inst_dir)

    dst = dest / name
    if not dst.exists():
        typer.echo(f"Skill '{name}' is not installed.", err=True)
        raise typer.Exit(1)

    shutil.rmtree(str(dst))

    manifest = Manifest.load(mpath)
    manifest.skills.pop(name, None)
    manifest.save(mpath)

    typer.echo(f"Uninstalled '{name}'.")
