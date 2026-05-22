from __future__ import annotations

import difflib
import hashlib
import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

from repo_skills.config import (
    ProviderRegistry,
    SkillEntry,
    compute_file_hashes,
    list_source_skills,
    load_provider_registry,
    load_skill_manifest,
    load_source_config,
    load_source_registry,
    resolve_branch,
    save_skill_manifest,
)
from repo_skills.errors import AppError, NoopError
from repo_skills.git import GitRepo

from ._app import app
from ._deps import resolve_git_repo
from ._utils import echo

MERGE_BRANCH_PREFIX = "skill-merge/"


def _find_in_provider(
    name: str,
    providers: ProviderRegistry,
    from_provider: str | None,
) -> Path | None:
    if from_provider is not None:
        pcfg = providers.require(from_provider)
        path = pcfg.resolve_path(name)
        return path if path.is_dir() else None

    for pcfg in providers.providers.values():
        path = pcfg.resolve_path(name)
        if path.is_dir():
            return path

    return None


def _resolve_untracked(name: str, from_provider: str | None) -> SkillEntry:
    providers = load_provider_registry()

    installed_path = _find_in_provider(name, providers, from_provider)
    if installed_path is None:
        raise AppError(f"Skill [green]{name}[/green] is not installed.")

    sources = load_source_registry()
    source_name: str | None = None
    source_skill_path: Path | None = None
    for sn, sentry in sources.sources.items():
        source_path = Path(sentry.path)
        if source_path.exists() and name in list_source_skills(source_path):
            source_name = sn
            source_cfg = load_source_config(source_path)
            source_skill_path = source_path / source_cfg.skills_dir / name
            break

    if source_name is None or source_skill_path is None:
        raise AppError(
            f"Skill [green]{name}[/green] is untracked"
            " and does not match any source."
        )

    return SkillEntry(
        source=source_name,
        commit=None,
        files=compute_file_hashes(source_skill_path),
    )


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
    no_commit: Annotated[
        bool,
        typer.Option("--no-commit", "-n", help="Stop before committing."),
    ] = False,
    continue_merge: Annotated[
        bool,
        typer.Option("--continue", help="Finalize a merge in progress."),
    ] = False,
    rebase: Annotated[
        bool,
        typer.Option("--rebase", help="Use rebase instead of merge."),
    ] = False,
    abort: Annotated[
        bool,
        typer.Option("--abort", help="Abort a merge in progress."),
    ] = False,
) -> None:
    if abort and continue_merge:
        raise AppError(
            "Cannot use [blue]--abort[/blue] and [blue]--continue[/blue] together."
        )

    if abort:
        _merge_abort()
        return

    if continue_merge:
        _merge_continue()
        return

    if name is None:
        raise AppError(
            "Skill name is required.\n\n"
            "Use [blue]--continue[/blue] to finalize a merge in progress."
        )

    _merge_start(
        name,
        from_provider=from_provider,
        offline=offline,
        no_commit=no_commit,
        rebase=rebase,
    )


def _merge_start(
    name: str,
    *,
    from_provider: str | None,
    offline: bool,
    no_commit: bool = False,
    rebase: bool = False,
) -> None:
    manifest = load_skill_manifest()
    if name not in manifest.skills:
        entry = _resolve_untracked(name, from_provider)
        manifest.skills[name] = entry
        save_skill_manifest(manifest)
    else:
        entry = manifest.skills[name]

    source_name = entry.source
    registry = load_source_registry()
    if source_name not in registry.sources:
        raise AppError(f"Source [green]{source_name}[/green] not found.")

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
        raise AppError(f"Repo has uncommitted changes.\n  repo: [dim]{git.path}[/dim]")

    source_cfg = load_source_config(source_path)
    target_branch = resolve_branch(source_cfg, git)
    if git.current_branch() != target_branch:
        git.checkout(target_branch)

    if not offline:
        git.pull()

    providers = load_provider_registry()
    provider_name = _resolve_provider(name, entry, providers, from_provider)

    pcfg = providers.require(provider_name)
    installed_path = pcfg.resolve_path(name)

    skill_src = source_path / source_cfg.skills_dir / name

    base_commit = entry.commit
    if base_commit is None:
        skill_rel = f"{source_cfg.skills_dir}/{name}"
        base_commit = _find_base_commit(git, skill_rel, entry, installed_path)

    branch_name = f"skill-merge/{provider_name}/{name}"
    if base_commit is not None:
        git.create_branch(branch_name, base_commit)
    else:
        git.create_orphan_branch(branch_name)

    _copy_provider_to_source(installed_path, skill_src)

    if no_commit:
        echo(
            "Files copied to source repo. Review, commit, and run"
            " [blue]skills merge --continue[/blue]."
        )
        return

    git.commit_all(f"chore: merge `{name}` from `{provider_name}`")

    use_merge = False
    if base_commit is not None and not rebase:
        git.checkout(target_branch)
        clean = git.merge(branch_name)
        use_merge = True
    elif base_commit is not None:
        clean = git.rebase(target_branch)
    else:
        clean = git.rebase_root(target_branch)

    if clean:
        _finalize(git, provider_name, name, already_merged=use_merge)
        return

    if use_merge:
        echo("[yellow]Warning:[/yellow] Merge has conflicts.\n")
    else:
        echo("[yellow]Warning:[/yellow] Rebase has conflicts.\n")

    echo("Resolve them, then run [blue]skills merge --continue[/blue].")


def _merge_continue() -> None:
    git = _detect_merge_repo()
    branch = _detect_merge_branch(git)
    provider_name, skill_name = _parse_merge_branch(branch)

    rebasing = git.is_rebasing()
    merging = git.is_merging()
    if rebasing:
        git.rebase_continue()
    elif merging:
        pass
    elif not git.is_clean():
        raise AppError(f"Repo has uncommitted changes.\n  repo: [dim]{git.path}[/dim]")

    _finalize(git, provider_name, skill_name)


def _finalize(
    git: GitRepo,
    provider_name: str,
    skill_name: str,
    *,
    already_merged: bool = False,
) -> None:
    branch = f"{MERGE_BRANCH_PREFIX}{provider_name}/{skill_name}"

    manifest = load_skill_manifest()
    entry = manifest.skills[skill_name]

    source_name = entry.source
    registry = load_source_registry()
    source_path = Path(registry.sources[source_name].path)
    source_cfg = load_source_config(source_path)
    skill_src = source_path / source_cfg.skills_dir / skill_name

    target_branch = resolve_branch(source_cfg, git)
    if not already_merged:
        git.checkout(target_branch)
        git.fast_forward(branch)

    providers = load_provider_registry()
    pcfg = providers.require(provider_name)
    installed_path = pcfg.resolve_path(skill_name)

    _copy_provider_to_source(skill_src, installed_path)

    new_hashes = compute_file_hashes(installed_path)
    empty = new_hashes == entry.files

    entry.commit = git.get_skill_commit(skill_name)
    entry.files = new_hashes
    save_skill_manifest(manifest)

    git.delete_branch(branch)

    if empty:
        echo(
            f"Nothing to merge for [green]{skill_name}[/green] " "— already up to date."
        )
        return

    echo(f"Merge complete for [green]{skill_name}[/green].")


def _merge_abort() -> None:
    git = _detect_merge_repo()
    branch = _detect_merge_branch(git)
    _, skill_name = _parse_merge_branch(branch)

    if git.is_rebasing():
        git.rebase_abort()
    elif git.is_merging():
        git.merge_abort()

    manifest = load_skill_manifest()
    entry = manifest.skills[skill_name]
    registry = load_source_registry()
    source_path = Path(registry.sources[entry.source].path)
    source_cfg = load_source_config(source_path)
    target_branch = resolve_branch(source_cfg, git)

    if git.current_branch() != target_branch:
        git.checkout(target_branch)

    git.delete_branch(branch)

    echo(f"Merge aborted for [green]{skill_name}[/green].")


def _detect_merge_repo() -> GitRepo:
    manifest = load_skill_manifest()
    for entry in manifest.skills.values():
        source_name = entry.source
        registry = load_source_registry()
        if source_name in registry.sources:
            source_path = Path(registry.sources[source_name].path)
            return resolve_git_repo(source_path)
    raise AppError("No source repo found.")


def _detect_merge_branch(git: GitRepo) -> str:
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

    raise AppError("No merge branch found.\n\n" "Run [blue]skills merge[/blue] first.")


def _parse_merge_branch(branch: str) -> tuple[str, str]:
    parts = branch.removeprefix(MERGE_BRANCH_PREFIX).split("/", 1)
    if len(parts) != 2:
        raise AppError(f"Invalid merge branch: [green]{branch}[/green]")
    return parts[0], parts[1]


def _resolve_provider(
    skill_name: str,
    entry: SkillEntry,
    providers: ProviderRegistry,
    from_provider: str | None,
) -> str:
    if from_provider is not None:
        providers.require(from_provider)
        return from_provider

    diverged: list[str] = []
    for pname, pcfg in providers.providers.items():
        installed_path = pcfg.resolve_path(skill_name)
        if not installed_path.exists():
            continue

        current_hashes = compute_file_hashes(installed_path)
        if current_hashes != entry.files:
            diverged.append(pname)

    if not diverged:
        raise NoopError(
            f"[green]{skill_name}[/green] is already synced. Nothing to merge."
        )

    if len(diverged) > 1:
        names = ", ".join(sorted(diverged))
        raise AppError(
            "Multiple providers have modified"
            f" [green]{skill_name}[/green] ({names}).\n\n"
            f"Use [blue]--from[/blue] to specify."
        )

    return diverged[0]


_MAX_SEARCH_COMMITS = 50


def _find_base_commit(
    git: GitRepo,
    skill_rel: str,
    entry: SkillEntry,
    installed_path: Path,
) -> str | None:
    commits = git.log_commits(skill_rel, _MAX_SEARCH_COMMITS)
    if not commits:
        return None

    best_commit: str | None = None
    best_distance = float("inf")

    for commit in commits:
        commit_hashes: dict[str, str] = {}
        for rel_path in entry.files:
            try:
                data = git.get_file_at_commit(commit, f"{skill_rel}/{rel_path}")
            except (KeyError, Exception):
                continue
            sha = hashlib.sha256(data).hexdigest()
            commit_hashes[rel_path] = f"sha256:{sha}"

        if commit_hashes == entry.files:
            return commit

        distance = _compute_distance(git, commit, skill_rel, entry, installed_path)
        if distance < best_distance:
            best_distance = distance
            best_commit = commit

    return best_commit


def _compute_distance(
    git: GitRepo,
    commit: str,
    skill_rel: str,
    entry: SkillEntry,
    installed_path: Path,
) -> int:
    total = 0
    all_paths = set(entry.files.keys())

    for rel_path in all_paths:
        try:
            commit_data = git.get_file_at_commit(commit, f"{skill_rel}/{rel_path}")
            commit_lines = commit_data.decode(errors="replace").splitlines(True)
        except (KeyError, Exception):
            commit_lines = []

        local_file = installed_path / rel_path
        if local_file.exists():
            installed_lines = local_file.read_text().splitlines(True)
        else:
            installed_lines = []

        if not commit_lines and not installed_lines:
            continue

        if not commit_lines:
            total += len(installed_lines)
            continue

        if not installed_lines:
            total += len(commit_lines)
            continue

        diff = difflib.unified_diff(commit_lines, installed_lines)
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                total += 1
            elif line.startswith("-") and not line.startswith("---"):
                total += 1

    return total


def _copy_provider_to_source(installed_path: Path, skill_src: Path) -> None:
    if skill_src.exists():
        shutil.rmtree(skill_src)
    shutil.copytree(installed_path, skill_src)
