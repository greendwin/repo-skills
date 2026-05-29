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
    InstalledSkill,
    Provider,
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceRegistry,
    SourceSkill,
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
    save_skill_manifest,
)
from repo_skills.errors import AppError, FileNotInCommitError, NoopError
from repo_skills.git import GitRepo
from repo_skills.utils import fmt_command, fmt_data, fmt_ident, fmt_path

from ._app import app
from ._deps import resolve_git_repo
from ._utils import echo, ensure_on_branch

MERGE_BRANCH_PREFIX = "skill-merge/"


@dataclass
class _MergeContext:
    provider_registry: ProviderRegistry
    source_registry: SourceRegistry
    manifest: SkillManifest


@app.command(help="Merge provider edits back into a source repo.")
def merge(
    *,
    skill_name: Annotated[
        Optional[str],
        typer.Argument(help="Skill to merge."),
    ] = None,
    from_provider: Annotated[
        Optional[str],
        typer.Option(
            "--from", help="Provider to merge from (required when ambiguous)."
        ),
    ] = None,
    to_source: Annotated[
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
            f"Cannot use {fmt_command('--abort')} and"
            f" {fmt_command('--continue')} together."
        )

    ctx = _MergeContext(
        provider_registry=load_provider_registry(),
        source_registry=load_source_registry(),
        manifest=load_skill_manifest(),
    )

    if abort:
        _merge_abort(ctx)
        return

    if continue_merge:
        _merge_continue(ctx)
        return

    if skill_name is None:
        raise AppError(
            "Skill name is required.",
            hint=f"Use {fmt_command('--continue')} to finalize a merge in progress.",
        )

    _merge_start(
        ctx,
        skill_name,
        from_provider=from_provider,
        to_source=to_source,
        offline=offline,
        no_commit=no_commit,
        rebase=rebase,
        search_base=search_base,
    )


def _merge_start(
    ctx: _MergeContext,
    skill_name: str,
    *,
    from_provider: str | None,
    to_source: str | None = None,
    offline: bool,
    no_commit: bool = False,
    rebase: bool = False,
    search_base: bool = False,
) -> None:
    provider = None
    if from_provider:
        provider = ctx.provider_registry.require(from_provider)

    source = None
    if to_source:
        source = ctx.source_registry.get_source(to_source, load_skills=True)

    installed = ctx.manifest.skills.get(skill_name)
    if installed is None:
        untracked = _resolve_untracked(
            ctx,
            skill_name=skill_name,
            provider=provider,
            source=source,
        )
        if untracked is None:
            _merge_orphan(
                ctx,
                skill_name,
                provider=provider,
                source=source,
                offline=offline,
                no_commit=no_commit,
            )
            return

        provider = untracked.provider

        # add untracked skill to manifest (aka detached skill)
        installed = ctx.manifest.register_skill(
            skill_name,
            source_name=untracked.source.name,
            commit=None,
            files=compute_file_hashes(
                untracked.source.repo_root / untracked.skill.rel_path
            ),
        )
        save_skill_manifest(ctx.manifest)

    source = ctx.source_registry.get_source(installed.source, load_skills=True)
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
            hint=f"Run {fmt_command('skills merge --continue')} to finish active merge "
            f"or {fmt_command('skills merge --abort')} to start over.",
        )

    target_branch = source.get_branch(git)
    ensure_on_branch(git, target_branch, pull=not offline)

    # check whether skill is in sync already
    if provider is not None:
        current_hashes = compute_file_hashes(provider.install_path / skill_name)
        if current_hashes == installed.files:
            # skill can be not attached
            _reattach_installed_skill(ctx.manifest, skill_name, installed, git)

            raise NoopError(
                f"{fmt_ident(skill_name)} is already synced. Nothing to merge."
            )

    # if no provider, search for provider that has skill that not in sync
    if provider is None:
        provider = _resolve_diverged_provider(
            ctx.provider_registry, skill_name, installed
        )

        # no diverged providers -- all in sync
        if provider is None:
            # TODO: this case is not covered, but we can possibly
            #       have here 'detached' skill, need to test it
            # _reattach_installed_skill(ctx.manifest, skill_name, installed, git)

            raise NoopError(
                f"{fmt_ident(skill_name)} is already synced. Nothing to merge."
            )

    skill = source.get_skill(skill_name)
    installed_path = provider.install_path / skill_name

    base_commit = _resolve_base_commit(
        git,
        skill,
        installed,
        installed_path,
        target_branch=target_branch,
        force=search_base,
    )

    branch_name = f"skill-merge/{provider.name}/{skill_name}"
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
            f" {fmt_command('skills merge --continue')}."
        )
        return

    git.commit_all(f"chore: merge `{skill_name}` from `{provider.name}`")

    use_merge = False
    if base_commit is not None and not rebase:
        git.checkout(target_branch)
        clean = git.merge(branch_name)
        use_merge = True
    elif base_commit is not None:
        clean = git.rebase(target_branch)
    else:
        clean = git.rebase_root(target_branch)

    if not clean:
        if use_merge:
            echo("[yellow]Warning:[/yellow] Merge has conflicts.\n")
        else:
            echo("[yellow]Warning:[/yellow] Rebase has conflicts.\n")

        echo(f"Resolve them, then run {fmt_command('skills merge --continue')}.")
        return

    _finalize(
        ctx,
        git,
        provider,
        skill_name,
        already_merged=use_merge,
    )


def _reattach_installed_skill(
    manifest: SkillManifest,
    skill_name: str,
    installed: InstalledSkill,
    git: GitRepo,
) -> None:
    if not installed.detached and installed.commit:
        return

    manifest.register_skill(
        skill_name,
        source_name=installed.source,
        commit=git.get_skill_commit(skill_name),
        files=dict(installed.files),
    )
    save_skill_manifest(manifest)


@dataclass
class _UntrackedSkill:
    provider: Provider
    source: Source
    skill: SourceSkill


def _resolve_untracked(
    ctx: _MergeContext,
    *,
    provider: Provider | None,
    skill_name: str,
    source: Source | None = None,
) -> _UntrackedSkill | None:
    provider = _find_skill_in_provider(ctx.provider_registry, provider, skill_name)

    if source is not None:
        skill = source.skills.get(skill_name)
        if skill is None:
            return None
        return _UntrackedSkill(provider, source, skill)

    matches: list[tuple[Source, SourceSkill]] = []
    for source_name in ctx.source_registry.sources:
        source = ctx.source_registry.get_source(source_name, load_skills=True)
        skill = source.skills.get(skill_name)
        if skill is not None:
            matches.append((source, skill))

    if len(matches) > 1:
        names = ", ".join(
            fmt_ident(s.name) for s, _ in sorted(matches, key=lambda x: x[0].name)
        )
        raise AppError(
            f"Multiple sources have {fmt_ident(skill_name)} ({names}).",
            hint=f"Use {fmt_command('--source')} to specify.",
        )

    if not matches:
        return None

    source, skill = matches[0]
    return _UntrackedSkill(provider, source, skill)


def _merge_orphan(
    ctx: _MergeContext,
    skill_name: str,
    *,
    provider: Provider | None,
    source: Source | None,
    offline: bool,
    no_commit: bool = False,
) -> None:
    if source is None:
        source = _resolve_orphan_source(ctx.source_registry)

    git = resolve_git_repo(source.repo_root)
    target_branch = source.get_branch(git)
    ensure_on_branch(git, target_branch, pull=not offline)

    provider = _find_skill_in_provider(ctx.provider_registry, provider, skill_name)

    installed_path = provider.install_path / skill_name
    skill_dst = source.repo_root / source.config.skills_dir / skill_name
    _copy_skill_with_replace(src=installed_path, dst=skill_dst)

    if no_commit:
        echo("Files copied to source repo. Review and commit manually.")
        return

    git.commit_all(f"chore: add `{skill_name}` from provider")

    manifest = load_skill_manifest()
    manifest.register_skill(
        skill_name,
        source_name=source.name,
        commit=git.get_skill_commit(skill_name),
        files=compute_file_hashes(installed_path),
    )
    save_skill_manifest(manifest)

    echo(f"Merge complete for {fmt_ident(skill_name)}.")


def _find_skill_in_provider(
    provider_registry: ProviderRegistry, provider: Provider | None, skill_name: str
) -> Provider:
    if provider:
        skill_path = provider.install_path / skill_name
        if not skill_path.is_dir():
            raise AppError(
                f"Skill {fmt_ident(skill_name)} is not installed "
                f"in {fmt_ident(provider.name)}."
            )

        return provider

    matches = []
    for prov in provider_registry.providers:
        skill_path = prov.install_path / skill_name
        if skill_path.is_dir():
            matches.append(prov)

    if len(matches) > 1:
        names = ", ".join(
            fmt_ident(p.name) for p in sorted(matches, key=lambda x: x.name)
        )
        raise AppError(
            f"Multiple providers have {fmt_ident(skill_name)} ({names}).",
            hint=f"Use {fmt_command('--from')} to specify.",
        )

    if not matches:
        raise AppError(f"Skill {fmt_ident(skill_name)} is not installed.")

    return matches[0]


def _copy_skill_with_replace(*, src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _resolve_diverged_provider(
    provider_registry: ProviderRegistry,
    skill_name: str,
    installed: InstalledSkill,
) -> Provider | None:
    # search providers for existing skills that installed but not synced
    diverged: list[Provider] = []
    for provider in provider_registry.providers:
        installed_path = provider.install_path / skill_name
        if not installed_path.exists():
            continue

        current_hashes = compute_file_hashes(installed_path)
        if current_hashes != installed.files:
            diverged.append(provider)

    if not diverged:
        return None

    if len(diverged) > 1:
        names = ", ".join(
            fmt_ident(p.name) for p in sorted(diverged, key=lambda x: x.name)
        )
        raise AppError(
            "Multiple providers have modified" f" {fmt_ident(skill_name)} ({names}).",
            hint=f"Use {fmt_command('--from')} to specify.",
        )

    return diverged[0]


def _resolve_base_commit(
    git: GitRepo,
    skill: SourceSkill,
    installed: InstalledSkill,
    installed_path: Path,
    *,
    target_branch: str,
    force: bool,
) -> str | None:
    if installed.commit and not force:
        if _check_reachability(git, installed.commit, target_branch):
            return installed.commit

        echo(
            f"[yellow]Warning:[/yellow] Stored commit"
            f" {fmt_ident(installed.commit[:8])} is dangling"
            " — searching for base commit."
        )

    r = _find_base_commit(git, skill.rel_path, installed, installed_path)

    if r is None:
        echo("No base commit found — rebase will be performed.")
        return None

    if r.distance == 0:
        echo(
            f"Base commit: {fmt_ident(r.commit[:8])} [dim](exact match)[/dim]\n"
            f"Message: {fmt_data(escape(r.message))}"
        )
        return r.commit

    echo(
        f"Base commit: {fmt_ident(r.commit[:8])} [dim](distance: {r.distance})[/dim]\n"
        f"Message: {fmt_data(escape(r.message))}"
    )
    return r.commit


def _check_reachability(git: GitRepo, commit: str, target_branch: str) -> bool:
    if git.is_ancestor(commit, target_branch):
        return True

    if git.commit_exists_in_any_branch(commit):
        raise AppError(
            f"Stored commit {fmt_ident(commit)} exists but is not on"
            f" branch {fmt_ident(target_branch)}.",
            hint=f"Use {fmt_command('--search-base')} to search for a base commit"
            f" on {fmt_ident(target_branch)}.",
        )

    return False


_MAX_SEARCH_COMMITS = 50


@dataclass
class _BestCommit:
    commit: str
    message: str
    distance: int


def _find_base_commit(
    git: GitRepo,
    skill_rel: str,
    installed: InstalledSkill,
    installed_path: Path,
) -> _BestCommit | None:
    commits = git.log_commits(skill_rel, _MAX_SEARCH_COMMITS)
    if not commits:
        return None

    best_commit: str | None = None
    best_distance = None

    for commit in commits:
        commit_hashes: dict[str, str] = {}
        for rel_path in installed.files:
            try:
                data = git.get_file_at_commit(commit, f"{skill_rel}/{rel_path}")
            except FileNotInCommitError:
                break  # missing file — disqualifies this commit

            sha = hashlib.sha256(data).hexdigest()
            commit_hashes[rel_path] = f"sha256:{sha}"
        else:  # all files found — evaluate this commit
            if commit_hashes == installed.files:
                best_commit = commit
                best_distance = 0
                break

            distance = _compute_distance(
                git, commit, skill_rel, installed, installed_path
            )
            if best_distance is None or best_distance > distance:
                best_commit = commit
                best_distance = distance

    if best_commit is None or best_distance is None:
        return None

    message = git.get_commit_message(best_commit)
    return _BestCommit(commit=best_commit, message=message, distance=best_distance)


def _merge_continue(ctx: _MergeContext) -> None:
    git = _detect_merge_repo(ctx)
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

    provider = ctx.provider_registry.require(provider_name)
    _finalize(ctx, git, provider, skill_name)


def _finalize(
    ctx: _MergeContext,
    git: GitRepo,
    provider: Provider,
    skill_name: str,
    *,
    already_merged: bool = False,
) -> None:
    merge_branch = f"{MERGE_BRANCH_PREFIX}{provider.name}/{skill_name}"

    installed = ctx.manifest.skills[skill_name]
    source = ctx.source_registry.get_source(installed.source, load_skills=True)
    skill = source.get_skill(skill_name)

    target_branch = source.get_branch(git)
    if not already_merged:
        git.checkout(target_branch)
        git.fast_forward(merge_branch)

    installed_path = provider.install_path / skill_name

    _copy_skill_with_replace(
        src=source.repo_root / skill.rel_path,
        dst=installed_path,
    )

    new_hashes = compute_file_hashes(installed_path)
    is_equal = new_hashes == installed.files

    ctx.manifest.register_skill(
        skill_name,
        source_name=installed.source,
        commit=git.get_skill_commit(skill_name),
        files=new_hashes,
    )
    save_skill_manifest(ctx.manifest)

    git.delete_branch(merge_branch)

    if is_equal:
        echo(f"Nothing to merge for {fmt_ident(skill_name)} — already up to date.")
        return

    echo(f"Merge complete for {fmt_ident(skill_name)}.")


def _merge_abort(ctx: _MergeContext) -> None:
    git = _detect_merge_repo(ctx)
    branch = _detect_merge_branch(git)
    _, skill_name = _parse_merge_branch(branch)

    if git.is_rebasing():
        git.rebase_abort()
    elif git.is_merging():
        git.merge_abort()

    intalled = ctx.manifest.skills[skill_name]
    source = ctx.source_registry.get_source(intalled.source, load_skills=False)

    target_branch = source.get_branch(git)
    if git.current_branch() != target_branch:
        git.checkout(target_branch)

    git.delete_branch(branch)

    echo(f"Merge aborted for {fmt_ident(skill_name)}.")


def _detect_merge_repo(ctx: _MergeContext) -> GitRepo:
    cwd = Path.cwd()
    candidates: list[GitRepo] = []
    for source in ctx.source_registry.sources.values():
        try:
            git = resolve_git_repo(source.repo_root)
        except AppError:
            continue

        if not _has_merge_branch(git):
            continue

        if cwd == source.repo_root or source.repo_root in cwd.parents:
            return git

        candidates.append(git)

    if not candidates:
        raise AppError(
            "No merge branch found in any source repo.",
            hint=f"Run {fmt_command('skills merge')} first.",
        )

    if len(candidates) > 1:
        names = ", ".join(fmt_ident(str(g.root)) for g in candidates)
        raise AppError(
            f"Multiple source repos have merge branches ({names}).",
            hint="Run from within the target source repo.",
        )

    return candidates[0]


def _has_merge_branch(git: GitRepo) -> bool:
    if git.current_branch().startswith(MERGE_BRANCH_PREFIX):
        return True
    return len(git.list_branches(f"{MERGE_BRANCH_PREFIX}*")) > 0


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
    installed: InstalledSkill,
    installed_path: Path,
) -> int:
    total = 0
    all_paths = set(installed.files.keys())

    for rel_path in all_paths:
        commit_data = git.get_file_at_commit(commit, f"{skill_rel}/{rel_path}")
        commit_lines = commit_data.decode(errors="replace").splitlines(True)

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


def _resolve_orphan_source(source_registry: SourceRegistry) -> Source:
    if not source_registry.sources:
        raise AppError("No sources registered.")

    if len(source_registry.sources) > 1:
        names = ", ".join(
            fmt_ident(name) for name in sorted(source_registry.sources.keys())
        )
        raise AppError(
            f"Multiple sources registered ({names}).",
            hint=f"Use {fmt_command('--source')} to specify.",
        )

    source_name = list(source_registry.sources)[0]
    return source_registry.get_source(source_name, load_skills=False)
