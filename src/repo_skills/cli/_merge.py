from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, NoReturn, Optional

import typer
from cli_error import CliError, CliExit

from repo_skills.config import (
    Baseline,
    ConfigContext,
    InstalledSkill,
    Provider,
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceSkill,
    compute_file_hashes,
    load_config_context,
    load_skill_manifest,
    make_baseline,
    read_skill_description,
    save_skill_manifest,
)
from repo_skills.console import reporter
from repo_skills.discovery import path_within
from repo_skills.git import FileNotInCommitError, GitRepo, ensure_on_branch
from repo_skills.utils import hash_content, normalize_line_endings, overwrite_dir

from ._app import app
from ._deps import prepare_source_repo, resolve_git_repo
from ._resolve_untracked import (
    find_skill_in_provider,
    resolve_orphan_source,
    resolve_untracked,
)

MERGE_BRANCH_PREFIX = "skill-merge/"


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
            "-s",
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
        raise CliError(
            "Cannot use [cmd]--abort[/cmd] and [cmd]--continue[/cmd] together."
        )

    ctx = load_config_context()

    if abort:
        _merge_abort(ctx)
        return

    if continue_merge:
        _merge_continue(ctx)
        return

    if skill_name is None:
        raise CliError("Skill name is required.").hint(
            "Use [cmd]--continue[/cmd] to finalize a merge in progress."
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
    ctx: ConfigContext,
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
        source = ctx.source_registry.load_source(to_source)

    installed = ctx.manifest.skills.get(skill_name)
    if installed is None:
        untracked = resolve_untracked(
            ctx.provider_registry,
            ctx.source_registry,
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
            baseline=None,
        )
        save_skill_manifest(ctx.manifest)

    source = ctx.source_registry.load_source(installed.source)
    skill = source.get_skill(skill_name)

    git = resolve_git_repo(source.repo_root)

    target_branch = source.get_branch(git)
    ensure_on_branch(git, target_branch, pull=not offline)

    # check whether skill is in sync already
    if provider is not None:
        current_hashes = compute_file_hashes(provider.install_path / skill_name)
        if installed.match_files(current_hashes):
            # match_files implies baseline is not None, so detached alone is enough
            _raise_in_sync(ctx, source, skill, git, reattached=installed.detached)

    # if no provider, search for provider that has skill that not in sync
    if provider is None:
        provider = _resolve_diverged_provider(
            ctx.provider_registry, skill_name, installed
        )

        # no diverged providers -- all in sync
        if provider is None:
            # no match_files guard, so a missing baseline must also trigger reattach
            _raise_in_sync(
                ctx,
                source,
                skill,
                git,
                reattached=installed.detached or not installed.baseline,
            )

    branch_name = f"skill-merge/{provider.name}/{skill_name}"
    if git.list_branches(branch_name):
        raise CliError(
            "Merge already in progress for [id]{skill}[/id].", skill=skill_name
        ).hint(
            "Run [cmd]skills merge --continue[/cmd] to finish active merge "
            "or [cmd]skills merge --abort[/cmd] to start over."
        )

    installed_path = provider.install_path / skill_name

    base_result = _resolve_base_commit(
        git,
        skill,
        installed,
        installed_path,
        target_branch=target_branch,
        force=search_base,
    )

    if base_result is not None and base_result.exact_match:
        # Provider files are byte-identical to a historical commit;
        # register baseline and skip branch/merge entirely.
        _finalyze_in_sync_skill(
            ctx,
            source=source,
            skill=skill,
            base_commit=base_result.commit,
            installed_path=installed_path,
            git=git,
        )
        return

    if base_result is not None:
        git.create_branch(branch_name, base_result.commit)
    else:
        git.create_orphan_branch(branch_name)

    overwrite_dir(installed_path, source.repo_root / skill.rel_path)

    if no_commit:
        reporter.print(
            "Files copied to source repo. Review, commit, and run"
            " [cmd]skills merge --continue[/cmd]."
        )
        return

    git.commit_all(f"chore: merge `{skill_name}` from `{provider.name}`")

    use_merge = False
    if base_result is not None and not rebase:
        git.checkout(target_branch)
        clean = git.merge(branch_name)
        use_merge = True
    elif base_result is not None:
        clean = git.rebase(target_branch)
    else:
        clean = git.rebase_root(target_branch)

    if not clean:
        if use_merge:
            reporter.warn("Merge has conflicts.\n")
        else:
            reporter.warn("Rebase has conflicts.\n")

        reporter.print("Resolve them, then run [cmd]skills merge --continue[/cmd].")
        return

    _finalize(
        ctx,
        git,
        provider,
        skill_name,
        already_merged=use_merge,
    )


def _finalyze_in_sync_skill(
    ctx: ConfigContext,
    git: GitRepo,
    source: Source,
    skill: SourceSkill,
    base_commit: str,
    installed_path: Path,
) -> None:
    baseline = make_baseline(base_commit, installed_path)
    ctx.manifest.register_skill(
        skill.name,
        source_name=source.name,
        baseline=baseline,
    )
    save_skill_manifest(ctx.manifest)

    latest = git.get_skill_commit(skill.rel_path)
    if base_commit == latest:
        reporter.print("[id]{name}[/id] is already up to date.", name=skill.name)
        return

    reporter.print(
        "[id]{name}[/id] matches a previous version.\n"
        "Run [cmd]skills update[/cmd] to pull the latest changes.",
        name=skill.name,
    )


def _raise_in_sync(
    ctx: ConfigContext,
    source: Source,
    skill: SourceSkill,
    git: GitRepo,
    *,
    reattached: bool,
) -> NoReturn:
    if not reattached:
        raise CliExit(
            "[id]{name}[/id] is already synced. Nothing to merge.", name=skill.name
        )

    _reattach_installed_skill(ctx.manifest, source, skill, git)
    raise CliExit(
        "[id]{name}[/id] is now tracked and in sync. Nothing to merge.",
        name=skill.name,
    )


def _reattach_installed_skill(
    manifest: SkillManifest,
    source: Source,
    skill: SourceSkill,
    git: GitRepo,
) -> None:
    baseline = make_baseline(
        git.get_skill_commit(skill.rel_path),
        source.repo_root / skill.rel_path,
    )
    manifest.register_skill(
        skill.name,
        source_name=source.name,
        baseline=baseline,
    )
    save_skill_manifest(manifest)


def _merge_orphan(
    ctx: ConfigContext,
    skill_name: str,
    *,
    provider: Provider | None,
    source: Source | None,
    offline: bool,
    no_commit: bool = False,
) -> None:
    if source is None:
        source = resolve_orphan_source(ctx.source_registry)

    repo = prepare_source_repo(source, pull=not offline)

    provider = find_skill_in_provider(
        ctx.provider_registry, provider=provider, skill_name=skill_name
    )
    installed_path = provider.install_path / skill_name
    active_dir = source.config.active_dir
    if active_dir is None:
        raise CliError(
            "Source [id]{source}[/id] has no skills directory configured.",
            source=source.name,
        ).hint("Run [cmd]skills source config --skills-dir <dir>[/cmd] to set one.")

    skill_rel_path = f"{active_dir}/{skill_name}"
    skill_dst = source.repo_root / skill_rel_path
    overwrite_dir(installed_path, skill_dst)

    if no_commit:
        reporter.print("Files copied to source repo. Review and commit manually.")
        return

    subject = f"feat: add `{skill_name}` skill"
    description = read_skill_description(installed_path)
    message = f"{subject}\n\n{description}" if description else subject
    repo.git.commit_all(message)

    commit = repo.git.get_skill_commit(skill_rel_path)

    manifest = load_skill_manifest()
    manifest.register_skill(
        skill_name,
        source_name=source.name,
        baseline=make_baseline(commit, skill_dst),
    )
    save_skill_manifest(manifest)

    reporter.print("Merge complete for [id]{skill}[/id].", skill=skill_name)


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

        if installed.baseline is None:
            diverged.append(provider)
            continue

        current_hashes = compute_file_hashes(installed_path)
        if current_hashes != installed.baseline.files:
            diverged.append(provider)

    if not diverged:
        return None

    if len(diverged) > 1:
        # BUG: comma should not be inside [id] marker
        names = ", ".join(p.name for p in sorted(diverged, key=lambda x: x.name))
        raise CliError(
            "Multiple providers have modified [id]{skill}[/id] ([id]{names}[/id]).",
            skill=skill_name,
            names=names,
        ).hint("Use [cmd]--from[/cmd] to specify.")

    return diverged[0]


@dataclass
class _ResolveBaseResult:
    commit: str
    exact_match: bool


def _resolve_base_commit(
    git: GitRepo,
    skill: SourceSkill,
    installed: InstalledSkill,
    installed_path: Path,
    *,
    target_branch: str,
    force: bool,
) -> _ResolveBaseResult | None:
    if installed.baseline and not force:
        if _check_reachability(git, installed.baseline.commit, target_branch):
            # caller already verified that provider files differ
            # from baseline before calling this function
            return _ResolveBaseResult(
                commit=installed.baseline.commit, exact_match=False
            )

        reporter.warn(
            "Stored commit"
            " [id]{commit}[/id] is dangling"
            " — searching for base commit.",
            commit=installed.baseline.commit[:8],
        )

    r = _find_base_commit(git, skill.rel_path, installed_path)

    if r is None:
        reporter.print("No base commit found — rebase will be performed.")
        return None

    if r.distance == 0:
        reporter.print(
            "Base commit: [id]{commit}[/id] [dim](exact match)[/dim]\n"
            "Message: [data]{message}[/data]",
            commit=r.commit[:8],
            message=r.message,
        )
        return _ResolveBaseResult(commit=r.commit, exact_match=True)

    reporter.print(
        "Base commit: [id]{commit}[/id] [dim](distance: {distance})[/dim]\n"
        "Message: [data]{message}[/data]",
        commit=r.commit[:8],
        distance=r.distance,
        message=r.message,
    )
    return _ResolveBaseResult(commit=r.commit, exact_match=False)


def _check_reachability(git: GitRepo, commit: str, target_branch: str) -> bool:
    if git.is_ancestor(commit, target_branch):
        return True

    if git.commit_exists_in_any_branch(commit):
        raise CliError(
            "Stored commit [id]{commit}[/id] exists but is not on"
            " branch [id]{branch}[/id].",
            commit=commit,
            branch=target_branch,
        ).hint(
            "Use [cmd]--search-base[/cmd] to search for a base commit"
            " on [id]{branch}[/id].",
            branch=target_branch,
        )

    return False


_MAX_SEARCH_COMMITS = 50


@dataclass
class _FindBestCommitResult:
    commit: str
    message: str
    distance: int


def _find_base_commit(
    git: GitRepo,
    skill_rel: str,
    installed_path: Path,
) -> _FindBestCommitResult | None:
    installed_hashes = compute_file_hashes(installed_path)
    if not installed_hashes:
        return None

    commits = git.log_commits(skill_rel, _MAX_SEARCH_COMMITS)
    if not commits:
        return None

    # installed files are loop-invariant — read and normalize them once
    installed_content: dict[str, bytes] = {
        rel_path: normalize_line_endings((installed_path / rel_path).read_bytes())
        for rel_path in installed_hashes
    }

    best_commit: str | None = None
    best_distance = None

    for commit in commits:
        score = _score_commit(
            git, commit, skill_rel, installed_hashes, installed_content
        )
        if score is None:
            continue  # a required installed file is missing — disqualified

        if score == 0:
            best_commit = commit
            best_distance = 0
            break

        if best_distance is None or best_distance > score:
            best_commit = commit
            best_distance = score

    if best_commit is None or best_distance is None:
        return None

    message = git.get_commit_message(best_commit)
    return _FindBestCommitResult(
        commit=best_commit,
        message=message,
        distance=best_distance,
    )


def _score_commit(
    git: GitRepo,
    commit: str,
    skill_rel: str,
    installed_hashes: dict[str, str],
    installed_content: dict[str, bytes],
) -> int | None:
    # fetch each installed file once and reuse the content for both the cheap
    # subset hash check and the distance computation
    commit_content: dict[str, bytes] = {}
    for rel_path in installed_hashes:
        try:
            raw = git.get_file_at_commit(commit, f"{skill_rel}/{rel_path}")
        except FileNotInCommitError:
            return None  # missing file — disqualifies this commit

        commit_content[rel_path] = normalize_line_endings(raw)

    commit_subset_hashes = {
        rel_path: hash_content(content) for rel_path, content in commit_content.items()
    }

    if commit_subset_hashes == installed_hashes:
        # the installed-file subset matches — only now run the expensive
        # full-tree check to confirm there are no extra files in the commit
        if git.commit_content_hashes(commit, skill_rel) == installed_hashes:
            return 0

        # extra files in the tree disqualify an exact match; the subset diff is
        # 0, so floor to 1 (0 is reserved for exact match)
        return 1

    distance = _compute_distance(
        commit_content, installed_content, set(installed_hashes.keys())
    )
    # distance must never read as 0 — reserved for exact match
    return max(1, distance)


def _merge_continue(ctx: ConfigContext) -> None:
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
        raise CliError("Repo has uncommitted changes.").prop_path("repo", git.root)

    provider = ctx.provider_registry.require(provider_name)
    _finalize(ctx, git, provider, skill_name)


def _finalize(
    ctx: ConfigContext,
    git: GitRepo,
    provider: Provider,
    skill_name: str,
    *,
    already_merged: bool = False,
) -> None:
    merge_branch = f"{MERGE_BRANCH_PREFIX}{provider.name}/{skill_name}"

    installed = ctx.manifest.skills[skill_name]
    source = ctx.source_registry.load_source(installed.source)
    skill = source.get_skill(skill_name)

    target_branch = source.get_branch(git)
    if not already_merged:
        git.checkout(target_branch)
        git.fast_forward(merge_branch)

    installed_path = provider.install_path / skill_name

    overwrite_dir(
        source.repo_root / skill.rel_path,
        installed_path,
    )

    new_hashes = compute_file_hashes(installed_path)
    is_equal = installed.match_files(new_hashes)

    ctx.manifest.register_skill(
        skill_name,
        source_name=installed.source,
        baseline=Baseline(
            # note: take latest commit for code, since we just finished
            #       merging and must be in sync
            commit=git.get_skill_commit(skill.rel_path),
            files=new_hashes,
        ),
    )
    save_skill_manifest(ctx.manifest)

    git.delete_branch(merge_branch)

    if is_equal:
        reporter.print(
            "Nothing to merge for [id]{skill}[/id] — already up to date.",
            skill=skill_name,
        )
        return

    reporter.print("Merge complete for [id]{skill}[/id].", skill=skill_name)


def _merge_abort(ctx: ConfigContext) -> None:
    git = _detect_merge_repo(ctx)
    branch = _detect_merge_branch(git)
    _, skill_name = _parse_merge_branch(branch)

    if git.is_rebasing():
        git.rebase_abort()
    elif git.is_merging():
        git.merge_abort()

    intalled = ctx.manifest.skills[skill_name]
    source = ctx.source_registry.get_source_no_skills(intalled.source)

    target_branch = source.get_branch(git)
    if git.current_branch() != target_branch:
        git.checkout(target_branch)

    git.delete_branch(branch)

    reporter.print("Merge aborted for [id]{skill}[/id].", skill=skill_name)


def _detect_merge_repo(ctx: ConfigContext) -> GitRepo:
    cwd = Path.cwd()
    candidates: list[GitRepo] = []
    for source in ctx.source_registry.sources.values():
        try:
            git = resolve_git_repo(source.repo_root)
        except CliError:
            continue

        if not _has_merge_branch(git):
            continue

        if path_within(cwd, source.repo_root):
            return git

        candidates.append(git)

    if not candidates:
        raise CliError("No merge branch found in any source repo.").hint(
            "Run [cmd]skills merge[/cmd] first."
        )

    if len(candidates) > 1:
        names = ", ".join(str(g.root) for g in candidates)
        raise CliError(
            "Multiple source repos have merge branches ([id]{names}[/id]).",
            names=names,
        ).hint("Run from within the target source repo.")

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
        names = ", ".join(sorted(branches))
        raise CliError(
            "Multiple merge branches found ([id]{names}[/id]).", names=names
        ).hint("Checkout the one to continue.")

    raise CliError("No merge branch found.").hint("Run [cmd]skills merge[/cmd] first.")


def _parse_merge_branch(branch: str) -> tuple[str, str]:
    parts = branch.removeprefix(MERGE_BRANCH_PREFIX).split("/", 1)
    if len(parts) != 2:
        raise CliError("Invalid merge branch: [id]{branch}[/id]", branch=branch)

    return parts[0], parts[1]


def _compute_distance(
    commit_content: dict[str, bytes],
    installed_content: dict[str, bytes],
    file_paths: set[str],
) -> int:
    # note: full-content equality (dist==0) is decided by the exact-match path
    # both dicts hold already-fetched, normalized blobs keyed by the
    # skill-relative posix path, so this function performs no disk or git I/O
    total = 0

    for rel_path in file_paths:
        commit_lines = commit_content[rel_path].decode(errors="replace").splitlines()

        installed_data = installed_content.get(rel_path)
        if installed_data is not None:
            installed_lines = installed_data.decode(errors="replace").splitlines()
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
