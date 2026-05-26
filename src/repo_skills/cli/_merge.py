from __future__ import annotations

import difflib
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.markup import escape

from repo_skills.config import (
    Source,
    SourceRegistry,
    compute_file_hashes,
    load_source_registry,
)
from repo_skills.config.deprecated import (
    ManifestSkill,
    ProviderRegistry,
    load_provider_registry,
    load_skill_manifest,
    save_skill_manifest,
)
from repo_skills.errors import AppError, NoopError
from repo_skills.git import GitRepo
from repo_skills.utils import fmt_command, fmt_ident, fmt_path

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
    source: Annotated[
        Optional[str],
        typer.Option(
            "--source",
            help="Target source (required for orphan skills when ambiguous).",
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
    search_base: Annotated[
        bool,
        typer.Option("--search-base", help="Search git history for base commit."),
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
            "Skill name is required.",
            hint="Use [blue]--continue[/blue] to finalize a merge in progress.",
        )

    _merge_start(
        name,
        from_provider=from_provider,
        to_source=source,
        offline=offline,
        no_commit=no_commit,
        rebase=rebase,
        search_base=search_base,
    )


def _merge_start(
    skill_name: str,
    *,
    from_provider: str | None,
    to_source: str | None = None,
    offline: bool,
    no_commit: bool = False,
    rebase: bool = False,
    search_base: bool = False,
) -> None:
    manifest = load_skill_manifest()
    providers = load_provider_registry()
    sources = load_source_registry()

    entry = manifest.skills.get(skill_name)
    if entry is None:
        entry = _resolve_untracked(
            sources,
            providers,
            skill_name=skill_name,
            from_provider=from_provider,
        )
        if entry is None:
            _merge_orphan(
                sources,
                providers,
                skill_name,
                from_provider=from_provider,
                to_source=to_source,
                offline=offline,
                no_commit=no_commit,
            )
            return

        manifest.skills[skill_name] = entry
        save_skill_manifest(manifest)

    source = sources.get_source(entry.source, load_skills=True)
    git = resolve_git_repo(source.repo_root)

    existing = git.list_branches(f"{MERGE_BRANCH_PREFIX}*")
    if existing:
        # TODO: we can start multiple parallel merges
        #       if they don't collide by provider+source
        names = ", ".join(
            fmt_ident(p.removeprefix(MERGE_BRANCH_PREFIX)) for p in sorted(existing)
        )
        raise AppError(
            f"Merge already in progress: {names}.",
            hint="Run [blue]skills merge --continue[/blue] to finish active merge "
            "or [blue]skills merge --abort[/blue] to start over.",
        )

    if not git.is_clean():
        raise AppError(
            "Repo has uncommitted changes.",
            props={"repo": fmt_path(git.root)},
        )

    target_branch = source.get_branch(git)
    if git.current_branch() != target_branch:
        git.checkout(target_branch)

    if not offline:
        git.pull()

    provider_name = _resolve_provider(skill_name, entry, providers, from_provider)

    provider_cfg = providers.require(provider_name)
    installed_path = provider_cfg.resolve_path(skill_name)

    skill = source.get_skill(skill_name)

    base_commit = entry.commit
    if base_commit is None or search_base:
        # TODO: test it when skill undere category subfolder
        r = _find_base_commit(git, skill.rel_path, entry, installed_path)
        # TODO: in case of orphan branch we must tell this to
        #       (i.e. that rebase will be performed)
        if r is not None:
            # TODO: rework this message
            if r.distance == 0:
                echo(
                    f"Base commit: {fmt_ident(r.commit)} "
                    f"(exact match, {escape(r.message)})"
                )
            else:
                echo(
                    f"Base commit: {fmt_ident(r.commit)}"
                    f" (distance: {r.distance}, {r.message})"
                )

            base_commit = r.commit

    branch_name = f"skill-merge/{provider_name}/{skill_name}"
    if base_commit is not None:
        git.create_branch(branch_name, base_commit)
    else:
        git.create_orphan_branch(branch_name)

    _copy_skill_with_replace(
        src=installed_path,
        dst=source.repo_root / skill.rel_path,
    )

    if no_commit:
        echo(
            "Files copied to source repo. Review, commit, and run"
            " [blue]skills merge --continue[/blue]."
        )
        return

    git.commit_all(f"chore: merge `{skill_name}` from `{provider_name}`")

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
        _finalize(git, provider_name, skill_name, already_merged=use_merge)
        return

    if use_merge:
        echo("[yellow]Warning:[/yellow] Merge has conflicts.\n")
    else:
        echo("[yellow]Warning:[/yellow] Rebase has conflicts.\n")

    echo("Resolve them, then run [blue]skills merge --continue[/blue].")


def _resolve_untracked(
    sources: SourceRegistry,
    providers: ProviderRegistry,
    *,
    from_provider: str | None,
    skill_name: str,
) -> ManifestSkill | None:
    installed_path = _find_in_provider(skill_name, providers, from_provider)
    if installed_path is None:
        raise AppError(f"Skill {fmt_ident(skill_name)} is not installed.")

    source = None
    skill = None
    for source_name in sources.sources:
        source = sources.get_source(source_name, load_skills=True)
        skill = source.skills.get(skill_name)
        if skill is not None:
            break

    if source is None or skill is None:
        return None

    return ManifestSkill(
        source=source.name,
        files=compute_file_hashes(source.repo_root / skill.rel_path),
    )


def _merge_orphan(
    sources: SourceRegistry,
    providers: ProviderRegistry,
    skill_name: str,
    *,
    from_provider: str | None,
    to_source: str | None,
    offline: bool,
    no_commit: bool = False,
) -> None:
    source = _resolve_orphan_source(sources, to_source)

    git = resolve_git_repo(source.repo_root)
    if not git.is_clean():
        raise AppError(
            "Repo has uncommitted changes.",
            props={"repo": fmt_path(git.root)},
        )

    target_branch = source.get_branch(git)
    if git.current_branch() != target_branch:
        git.checkout(target_branch)

    if not offline:
        git.pull()

    installed_path = _find_in_provider(skill_name, providers, from_provider)
    if installed_path is None:
        raise AppError(f"Skill {fmt_ident(skill_name)} is not installed.")

    skill_dst = source.repo_root / source.config.skills_dir / skill_name
    _copy_skill_with_replace(src=installed_path, dst=skill_dst)

    if no_commit:
        echo("Files copied to source repo. Review and commit manually.")
        return

    git.commit_all(f"chore: add `{skill_name}` from provider")

    manifest = load_skill_manifest()
    manifest.skills[skill_name] = ManifestSkill(
        source=source.name,
        commit=git.get_skill_commit(skill_name),
        files=compute_file_hashes(installed_path),
    )
    save_skill_manifest(manifest)

    echo(f"Merge complete for {fmt_ident(skill_name)}.")


def _find_in_provider(
    skill_name: str, providers: ProviderRegistry, from_provider: str | None
) -> Path | None:
    if from_provider is not None:
        pr = providers.require(from_provider)
        skill_path = pr.resolve_path(skill_name)
        return skill_path if skill_path.is_dir() else None

    for pr in providers.providers.values():
        skill_path = pr.resolve_path(skill_name)
        if skill_path.is_dir():
            return skill_path

    return None


def _copy_skill_with_replace(*, src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _resolve_provider(
    skill_name: str,
    entry: ManifestSkill,
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
        raise NoopError(f"{fmt_ident(skill_name)} is already synced. Nothing to merge.")

    if len(diverged) > 1:
        names = ", ".join(fmt_ident(name) for name in sorted(diverged))
        raise AppError(
            "Multiple providers have modified" f" {fmt_ident(skill_name)} ({names}).",
            hint=f"Use {fmt_command('--from')} to specify.",
        )

    return diverged[0]


_MAX_SEARCH_COMMITS = 50


@dataclass
class _BestCommit:
    commit: str
    message: str
    distance: int


def _find_base_commit(
    git: GitRepo,
    skill_rel: str,
    entry: ManifestSkill,
    installed_path: Path,
) -> _BestCommit | None:
    commits = git.log_commits(skill_rel, _MAX_SEARCH_COMMITS)
    if not commits:
        return None

    best_commit: str | None = None
    best_distance = None

    for commit in commits:
        commit_hashes: dict[str, str] = {}
        for rel_path in entry.files:
            # TODO: it's invalid to silently skip all exceptions
            #       we can wrongly match base commit
            try:
                data = git.get_file_at_commit(commit, f"{skill_rel}/{rel_path}")
            except Exception:
                continue

            sha = hashlib.sha256(data).hexdigest()
            commit_hashes[rel_path] = f"sha256:{sha}"

        if commit_hashes == entry.files:
            best_commit = commit
            best_distance = 0
            break

        distance = _compute_distance(git, commit, skill_rel, entry, installed_path)
        if best_distance is None or best_distance > distance:
            best_commit = commit
            best_distance = distance

    if best_commit is None or best_distance is None:
        return None

    message = git.get_commit_message(best_commit)
    return _BestCommit(commit=best_commit, message=message, distance=best_distance)


def _merge_continue() -> None:
    sources = load_source_registry()
    git = _detect_merge_repo(sources)
    branch = _detect_merge_branch(git)
    provider_name, skill_name = _parse_merge_branch(branch)

    rebasing = git.is_rebasing()
    merging = git.is_merging()
    if rebasing:
        git.rebase_continue()
    elif merging:
        pass
    elif not git.is_clean():
        raise AppError(
            "Repo has uncommitted changes.",
            props={"repo": fmt_path(git.root)},
        )

    _finalize(git, provider_name, skill_name)


def _finalize(
    git: GitRepo,
    provider_name: str,
    skill_name: str,
    *,
    already_merged: bool = False,
) -> None:
    merge_branch = f"{MERGE_BRANCH_PREFIX}{provider_name}/{skill_name}"

    manifest = load_skill_manifest()
    entry = manifest.skills[skill_name]

    sources = load_source_registry()
    source = sources.get_source(entry.source, load_skills=True)
    skill = source.get_skill(skill_name)

    target_branch = source.get_branch(git)
    if not already_merged:
        git.checkout(target_branch)
        git.fast_forward(merge_branch)

    providers = load_provider_registry()
    pcfg = providers.require(provider_name)
    installed_path = pcfg.resolve_path(skill_name)

    _copy_skill_with_replace(
        src=source.repo_root / skill.rel_path,
        dst=installed_path,
    )

    new_hashes = compute_file_hashes(installed_path)

    # TODO: if equal, then why do we copy?
    is_equal = new_hashes == entry.files

    entry.commit = git.get_skill_commit(skill_name)
    entry.files = new_hashes
    save_skill_manifest(manifest)

    git.delete_branch(merge_branch)

    if is_equal:
        echo(f"Nothing to merge for {fmt_ident(skill_name)} — already up to date.")
        return

    echo(f"Merge complete for {fmt_ident(skill_name)}.")


def _merge_abort() -> None:
    sources = load_source_registry()
    git = _detect_merge_repo(sources)
    branch = _detect_merge_branch(git)
    _, skill_name = _parse_merge_branch(branch)

    if git.is_rebasing():
        git.rebase_abort()
    elif git.is_merging():
        git.merge_abort()

    manifest = load_skill_manifest()
    entry = manifest.skills[skill_name]
    source = sources.get_source(entry.source, load_skills=False)

    target_branch = source.get_branch(git)
    if git.current_branch() != target_branch:
        git.checkout(target_branch)

    git.delete_branch(branch)

    echo(f"Merge aborted for {fmt_ident(skill_name)}.")


def _detect_merge_repo(sources: SourceRegistry) -> GitRepo:
    # TODO: BUG: this is just wrong, it peak first source
    # we need to check either '--source' field or cwd()

    manifest = load_skill_manifest()
    for entry in manifest.skills.values():
        source_entry = sources.sources.get(entry.source)
        if source_entry is not None:
            return resolve_git_repo(source_entry.repo_root)

    raise AppError("No source repo found.")


def _detect_merge_branch(git: GitRepo) -> str:
    current = git.current_branch()
    if current.startswith(MERGE_BRANCH_PREFIX):
        return current

    branches = git.list_branches(f"{MERGE_BRANCH_PREFIX}*")
    if len(branches) == 1:
        return branches[0]

    if len(branches) > 1:
        names = ", ".join(fmt_ident(n) for n in sorted(branches))
        raise AppError(
            f"Multiple merge branches found ({names}).",
            hint="Checkout the one to continue.",
        )

    raise AppError(
        "No merge branch found.",
        hint=f"Run {fmt_command('skills merge')} first.",
    )


def _parse_merge_branch(branch: str) -> tuple[str, str]:
    parts = branch.removeprefix(MERGE_BRANCH_PREFIX).split("/", 1)
    if len(parts) != 2:
        raise AppError(f"Invalid merge branch: {fmt_ident(branch)}")
    return parts[0], parts[1]


def _compute_distance(
    git: GitRepo,
    commit: str,
    skill_rel: str,
    entry: ManifestSkill,
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


def _resolve_orphan_source(sources: SourceRegistry, to_source: str | None) -> Source:
    if to_source:
        return sources.get_source(to_source, load_skills=False)

    if not sources.sources:
        raise AppError("No sources registered.")

    if len(sources.sources) > 1:
        names = ", ".join(fmt_ident(name) for name in sorted(sources.sources.keys()))
        raise AppError(
            f"Multiple sources registered ({names}).",
            hint="Use [blue]--source[/blue] to specify.",
        )

    source_name = list(sources.sources)[0]
    return sources.get_source(source_name, load_skills=False)
