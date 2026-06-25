from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, NoReturn, Optional

import typer
from rich.markup import escape

from repo_skills.config import (
    Baseline,
    ConfigContext,
    InstalledSkill,
    Provider,
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceRegistry,
    SourceSkill,
    compute_file_hashes,
    default_config_path,
    load_config_context,
    load_skill_manifest,
    make_baseline,
    read_skill_description,
    save_skill_manifest,
)
from repo_skills.console import console, fmt_command, fmt_data, fmt_ident, fmt_path
from repo_skills.discovery import path_within
from repo_skills.errors import AppError, FileNotInCommitError, NoopError
from repo_skills.git import GitRepo, ensure_on_branch
from repo_skills.utils import hash_content, normalize_line_endings, overwrite_dir

from ._app import app
from ._deps import prepare_source_repo, resolve_git_repo

# Deferred --keep-source intent rides in the keep-prefixed branch *name*, so a
# resumed `--continue`/`--abort` derives it from the branch — no persisted state.
MERGE_BRANCH_STEM = "skill-merge"
MERGE_BRANCH_PREFIX = f"{MERGE_BRANCH_STEM}/"
MERGE_KEEP_BRANCH_PREFIX = f"{MERGE_BRANCH_STEM}-keep/"
_MERGE_PREFIXES = (MERGE_KEEP_BRANCH_PREFIX, MERGE_BRANCH_PREFIX)


def _cleanup_legacy_merge_state() -> None:
    # Pre-upgrade keep-source persistence wrote merge-state.json; that mechanism
    # is gone (intent now rides the branch name), so best-effort unlink the stale
    # artifact on any resume. Note: deferred keep-source merges from before the
    # upgrade must be re-run.
    default_config_path("merge-state.json").unlink(missing_ok=True)


def _merge_branch_name(
    provider_name: str, skill_name: str, *, keep_source: bool
) -> str:
    prefix = MERGE_KEEP_BRANCH_PREFIX if keep_source else MERGE_BRANCH_PREFIX
    return f"{prefix}{provider_name}/{skill_name}"


def _merge_branch_prefix(branch: str) -> str | None:
    for prefix in _MERGE_PREFIXES:
        if branch.startswith(prefix):
            return prefix
    return None


def _merged_still_tracking(
    skill_name: str, target_name: str, old_source: str | None
) -> str:
    # keep-source publish: content lands in target, manifest still tracks old.
    # old_source None (entry vanished mid-merge) => no tracking suffix.
    tracking = (
        f" (still tracking {fmt_ident(old_source)})" if old_source is not None else ""
    )
    return f"Merged {fmt_ident(skill_name)} into {fmt_ident(target_name)}{tracking}."


@dataclass
class _OrphanAdd:
    skill_rel_path: str
    skill_dst: Path
    committed: bool  # False when stopped early for --no-commit


def _orphan_add_commit(
    git: GitRepo,
    *,
    source: Source,
    installed_path: Path,
    skill_name: str,
    no_commit: bool,
) -> _OrphanAdd:
    # active_dir guard + copy into source + `feat: add` commit, shared by the
    # orphan-merge and orphan-retarget paths; callers diff in manifest/messaging.
    active_dir = source.config.active_dir
    if active_dir is None:
        raise AppError(
            f"Source {fmt_ident(source.name)} has no skills directory configured.",
            hint=f"Run {fmt_command('skills source config --skills-dir <dir>')} "
            "to set one.",
        )

    skill_rel_path = f"{active_dir}/{skill_name}"
    skill_dst = source.repo_root / skill_rel_path
    overwrite_dir(installed_path, skill_dst)

    if no_commit:
        console.print("Files copied to source repo. Review and commit manually.")
        return _OrphanAdd(skill_rel_path, skill_dst, committed=False)

    subject = f"feat: add `{skill_name}` skill"
    description = read_skill_description(installed_path)
    message = f"{subject}\n\n{description}" if description else subject
    git.commit_all(message)

    return _OrphanAdd(skill_rel_path, skill_dst, committed=True)


def _finalize_merge_branch(
    git: GitRepo,
    *,
    target_branch: str,
    branch_name: str,
    use_merge: bool,
    src: Path,
    dst: Path,
) -> None:
    # shared git completion: land the merge branch onto target, publish content,
    # drop the branch. `src`/`dst` carry direction explicitly — same direction
    # (repo -> installed_path), different repo: same-source copies
    # source.repo_root/rel_path; retarget copies target.repo_root/rel_path.
    if not use_merge:
        git.checkout(target_branch)
        git.fast_forward(branch_name)

    overwrite_dir(src, dst)
    git.delete_branch(branch_name)


def _write_retarget_manifest(
    ctx: ConfigContext,
    git: GitRepo,
    *,
    skill_name: str,
    rel_path: str,
    content_dir: Path,
    target_name: str,
    old_source: str,  # callers guarantee non-None
    keep_source: bool,
) -> None:
    # publish-or-keep sink: keep-source leaves the manifest tracking old_source.
    if keep_source:
        console.print(_merged_still_tracking(skill_name, target_name, old_source))
        return

    commit = git.get_skill_commit(rel_path)
    ctx.manifest.register_skill(
        skill_name,
        source_name=target_name,
        baseline=make_baseline(commit, content_dir),
    )
    save_skill_manifest(ctx.manifest)

    console.print(
        f"Retargeted {fmt_ident(skill_name)}: now tracking {fmt_ident(target_name)}"
        f" (was {fmt_ident(old_source)})."
    )


def _run_branch_merge(
    ctx: ConfigContext,
    git: GitRepo,
    *,
    skill: SourceSkill,
    installed: InstalledSkill,
    provider: Provider,
    skill_name: str,
    working_root: Path,
    target_branch: str,
    force: bool,
    no_commit: bool,
    rebase: bool,
    keep_source: bool,
    on_exact_match: Callable[[str], None],
    on_finalize: Callable[[GitRepo, str, bool], None],
) -> None:
    # Shared branch-merge engine for same-source and cross-source paths. Diffs
    # are parameterized: working_root (where content lands), force (base search),
    # keep-source (encoded in the branch name, see module note), and the
    # exact-match / finalize tails.
    branch_name = _merge_branch_name(provider.name, skill_name, keep_source=keep_source)
    # any in-progress merge for this skill (either prefix) blocks a fresh one
    if any(
        _parse_merge_branch(b) == (provider.name, skill_name)
        for b in _list_merge_branches(git)
    ):
        raise AppError(
            f"Merge already in progress for {fmt_ident(skill_name)}.",
            hint=f"Run {fmt_command('skills merge --continue')} to finish active merge "
            f"or {fmt_command('skills merge --abort')} to start over.",
        )

    installed_path = provider.install_path / skill_name

    base_result = _resolve_base_commit(
        git,
        skill,
        installed,
        installed_path,
        target_branch=target_branch,
        force=force,
    )

    if base_result is not None and base_result.exact_match:
        on_exact_match(base_result.commit)
        return

    if base_result is not None:
        git.create_branch(branch_name, base_result.commit)
    else:
        git.create_orphan_branch(branch_name)

    overwrite_dir(installed_path, working_root / skill.rel_path)

    if no_commit:
        # deferred finish resumes via _merge_continue/_finalize; the keep-source
        # intent already rides in branch_name, nothing extra to persist.
        console.print(
            "Files copied to source repo. Review, commit, and run"
            f" {fmt_command('skills merge --continue')}."
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
            console.print("[yellow]Warning:[/yellow] Merge has conflicts.\n")
        else:
            console.print("[yellow]Warning:[/yellow] Rebase has conflicts.\n")

        console.print(
            f"Resolve them, then run {fmt_command('skills merge --continue')}."
        )
        return

    on_finalize(git, branch_name, use_merge)


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
    keep_source: Annotated[
        bool,
        typer.Option(
            "--keep-source",
            help="Merge content into the target source but keep tracking the"
            " current source.",
        ),
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

    ctx = load_config_context()

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
        keep_source=keep_source,
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
    keep_source: bool = False,
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
            baseline=None,
        )
        save_skill_manifest(ctx.manifest)

    # cross-source: --source X given and X differs from tracking source Y.
    # Work against X, ignoring the Y baseline entirely.
    if to_source is not None and to_source != installed.source:
        _merge_retarget(
            ctx,
            skill_name,
            installed=installed,
            target=ctx.source_registry.load_source(to_source),
            provider=provider,
            keep_source=keep_source,
            offline=offline,
            no_commit=no_commit,
            rebase=rebase,
        )
        return

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

    installed_path = provider.install_path / skill_name

    def _on_exact_match(base_commit: str) -> None:
        # Provider files are byte-identical to a historical commit;
        # register baseline and skip branch/merge entirely.
        _finalize_in_sync_skill(
            ctx,
            source=source,
            skill=skill,
            base_commit=base_commit,
            installed_path=installed_path,
            git=git,
        )

    def _on_finalize(git: GitRepo, branch_name: str, use_merge: bool) -> None:
        _finalize(
            ctx,
            git,
            provider,
            skill_name,
            merge_branch=branch_name,
            already_merged=use_merge,
        )

    _run_branch_merge(
        ctx,
        git,
        skill=skill,
        installed=installed,
        provider=provider,
        skill_name=skill_name,
        working_root=source.repo_root,
        target_branch=target_branch,
        force=search_base,
        no_commit=no_commit,
        rebase=rebase,
        keep_source=False,
        on_exact_match=_on_exact_match,
        on_finalize=_on_finalize,
    )


def _merge_retarget(
    ctx: ConfigContext,
    skill_name: str,
    *,
    installed: InstalledSkill,
    target: Source,
    provider: Provider | None,
    keep_source: bool,
    offline: bool,
    no_commit: bool,
    rebase: bool,
) -> None:
    old_source = installed.source

    git = resolve_git_repo(target.repo_root)
    target_branch = target.get_branch(git)
    ensure_on_branch(git, target_branch, pull=not offline)

    # has-skill provider resolution; Y-baseline divergence is irrelevant for X
    provider = _find_skill_in_provider(ctx.provider_registry, provider, skill_name)

    skill = target.skills.get(skill_name)
    if skill is None:
        # X lacks the skill: orphan-add into X, then retarget the manifest to X.
        _retarget_orphan_add(
            ctx,
            git,
            skill_name,
            target=target,
            provider=provider,
            old_source=old_source,
            keep_source=keep_source,
            no_commit=no_commit,
        )
        return

    installed_path = provider.install_path / skill_name

    def _on_exact_match(base_commit: str) -> None:
        _retarget_in_sync(
            ctx,
            git,
            target=target,
            skill=skill,
            base_commit=base_commit,
            installed_path=installed_path,
            old_source=old_source,
            keep_source=keep_source,
        )

    def _on_finalize(git: GitRepo, branch_name: str, use_merge: bool) -> None:
        # shared git plumbing; retarget keeps its own manifest write + messaging.
        _finalize_merge_branch(
            git,
            target_branch=target_branch,
            branch_name=branch_name,
            use_merge=use_merge,
            src=target.repo_root / skill.rel_path,
            dst=installed_path,
        )

        _write_retarget_manifest(
            ctx,
            git,
            skill_name=skill.name,
            rel_path=skill.rel_path,
            content_dir=installed_path,
            target_name=target.name,
            old_source=old_source,
            keep_source=keep_source,
        )

    # force base search over X's history — installed.baseline is a Y commit
    _run_branch_merge(
        ctx,
        git,
        skill=skill,
        installed=installed,
        provider=provider,
        skill_name=skill_name,
        working_root=target.repo_root,
        target_branch=target_branch,
        force=True,
        no_commit=no_commit,
        rebase=rebase,
        keep_source=keep_source,
        on_exact_match=_on_exact_match,
        on_finalize=_on_finalize,
    )


def _retarget_in_sync(
    ctx: ConfigContext,
    git: GitRepo,
    *,
    target: Source,
    skill: SourceSkill,
    base_commit: str,
    installed_path: Path,
    old_source: str,
    keep_source: bool,
) -> None:
    if keep_source:
        # content already lives in X at base_commit; leave the manifest untouched
        console.print(_merged_still_tracking(skill.name, target.name, old_source))
        return

    baseline = make_baseline(base_commit, installed_path)
    ctx.manifest.register_skill(
        skill.name,
        source_name=target.name,
        baseline=baseline,
    )
    save_skill_manifest(ctx.manifest)

    # if the matched commit is not X's tip, warn it is a previous version (cf.
    # _finalize_in_sync_skill) instead of claiming a clean "already matches".
    latest = git.get_skill_commit(skill.rel_path)
    if base_commit != latest:
        console.print(
            f"{fmt_ident(skill.name)} matches a previous version of"
            f" {fmt_ident(target.name)} — now tracking {fmt_ident(target.name)}"
            f" (was {fmt_ident(old_source)}).\n"
            f"Run {fmt_command('skills update')} to pull the latest changes."
        )
        return

    console.print(
        f"{fmt_ident(skill.name)} already matches {fmt_ident(target.name)}"
        f" — now tracking {fmt_ident(target.name)} (was {fmt_ident(old_source)})."
    )


def _retarget_orphan_add(
    ctx: ConfigContext,
    git: GitRepo,
    skill_name: str,
    *,
    target: Source,
    provider: Provider,
    old_source: str,
    keep_source: bool,
    no_commit: bool,
) -> None:
    added = _orphan_add_commit(
        git,
        source=target,
        installed_path=provider.install_path / skill_name,
        skill_name=skill_name,
        no_commit=no_commit,
    )
    if not added.committed:
        return

    _write_retarget_manifest(
        ctx,
        git,
        skill_name=skill_name,
        rel_path=added.skill_rel_path,
        content_dir=added.skill_dst,
        target_name=target.name,
        old_source=old_source,
        keep_source=keep_source,
    )


def _finalize_in_sync_skill(
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
        console.print(f"{fmt_ident(skill.name)} is already up to date.")
        return

    console.print(
        f"{fmt_ident(skill.name)} matches a previous version.\n"
        f"Run {fmt_command('skills update')} to pull the latest changes."
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
        raise NoopError(f"{fmt_ident(skill.name)} is already synced. Nothing to merge.")

    _reattach_installed_skill(ctx.manifest, source, skill, git)
    raise NoopError(
        f"{fmt_ident(skill.name)} is now tracked and in sync. Nothing to merge."
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


@dataclass
class _UntrackedSkill:
    provider: Provider
    source: Source
    skill: SourceSkill


def _resolve_untracked(
    ctx: ConfigContext,
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
        source = ctx.source_registry.load_source(source_name)
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
    ctx: ConfigContext,
    skill_name: str,
    *,
    provider: Provider | None,
    source: Source | None,
    offline: bool,
    no_commit: bool = False,
) -> None:
    if source is None:
        source = _resolve_orphan_source(ctx.source_registry)

    repo = prepare_source_repo(source, pull=not offline)

    provider = _find_skill_in_provider(ctx.provider_registry, provider, skill_name)

    added = _orphan_add_commit(
        repo.git,
        source=source,
        installed_path=provider.install_path / skill_name,
        skill_name=skill_name,
        no_commit=no_commit,
    )
    if not added.committed:
        return

    commit = repo.git.get_skill_commit(added.skill_rel_path)

    manifest = load_skill_manifest()
    manifest.register_skill(
        skill_name,
        source_name=source.name,
        baseline=make_baseline(commit, added.skill_dst),
    )
    save_skill_manifest(manifest)

    console.print(f"Merge complete for {fmt_ident(skill_name)}.")


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
        names = ", ".join(
            fmt_ident(p.name) for p in sorted(diverged, key=lambda x: x.name)
        )
        raise AppError(
            "Multiple providers have modified" f" {fmt_ident(skill_name)} ({names}).",
            hint=f"Use {fmt_command('--from')} to specify.",
        )

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

        console.print(
            f"[yellow]Warning:[/yellow] Stored commit"
            f" {fmt_ident(installed.baseline.commit[:8])} is dangling"
            " — searching for base commit."
        )

    r = _find_base_commit(git, skill.rel_path, installed_path)

    if r is None:
        console.print("No base commit found — rebase will be performed.")
        return None

    if r.distance == 0:
        console.print(
            f"Base commit: {fmt_ident(r.commit[:8])} [dim](exact match)[/dim]\n"
            f"Message: {fmt_data(escape(r.message))}"
        )
        return _ResolveBaseResult(commit=r.commit, exact_match=True)

    console.print(
        f"Base commit: {fmt_ident(r.commit[:8])} [dim](distance: {r.distance})[/dim]\n"
        f"Message: {fmt_data(escape(r.message))}"
    )
    return _ResolveBaseResult(commit=r.commit, exact_match=False)


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


def _resolve_active_merge(ctx: ConfigContext) -> tuple[GitRepo, str, str, str]:
    # single home for the deferred-resume entry: fold legacy cleanup into the
    # one boundary that locates the in-progress merge's repo/branch/skill.
    _cleanup_legacy_merge_state()
    git = _detect_merge_repo(ctx)
    branch = _detect_merge_branch(git)
    provider_name, skill_name = _parse_merge_branch(branch)
    return git, branch, provider_name, skill_name


def _merge_continue(ctx: ConfigContext) -> None:
    git, branch, provider_name, skill_name = _resolve_active_merge(ctx)

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
    _finalize(ctx, git, provider, skill_name, merge_branch=branch)


def _finalize(
    ctx: ConfigContext,
    git: GitRepo,
    provider: Provider,
    skill_name: str,
    *,
    merge_branch: str,
    already_merged: bool = False,
) -> None:
    # keep-source intent rides in the branch *name* (keep-prefixed); a resumed
    # --continue reads it straight off `merge_branch`, so it self-invalidates with
    # the branch and never leaks to a later same-source merge.
    keep_source = _merge_branch_prefix(merge_branch) == MERGE_KEEP_BRANCH_PREFIX

    # derive source from the repo holding the merge branch, not installed.source:
    # a cross-source retarget runs the merge in X's repo while the manifest still
    # tracks Y, so resuming via installed.source (Y) would corrupt the entry.
    source = _source_for_repo(ctx.source_registry, git)
    skill = source.get_skill(skill_name)

    target_branch = source.get_branch(git)
    installed_path = provider.install_path / skill_name

    _finalize_merge_branch(
        git,
        target_branch=target_branch,
        branch_name=merge_branch,
        use_merge=already_merged,
        src=source.repo_root / skill.rel_path,
        dst=installed_path,
    )

    prev = ctx.manifest.skills.get(skill_name)

    # keep-source: finalize content into X but leave the manifest entry untouched
    # (and never resurrect an entry removed mid-merge → prev is None).
    if keep_source:
        # prev gone (entry removed mid-merge): nothing to keep tracking
        old_source = prev.source if prev is not None else None
        console.print(_merged_still_tracking(skill_name, source.name, old_source))
        return

    is_same_source = prev is not None and prev.source == source.name

    new_hashes = compute_file_hashes(installed_path)

    # "already up to date" only applies to a same-source resume; a cross-source
    # retarget always changes the tracking source, so it never reads as a no-op.
    # is_same_source implies prev is not None (see above).
    is_equal = is_same_source and prev is not None and prev.match_files(new_hashes)

    ctx.manifest.register_skill(
        skill_name,
        source_name=source.name,
        baseline=Baseline(
            # note: take latest commit for code, since we just finished
            #       merging and must be in sync
            commit=git.get_skill_commit(skill.rel_path),
            files=new_hashes,
        ),
    )
    save_skill_manifest(ctx.manifest)

    if is_equal:
        console.print(
            f"Nothing to merge for {fmt_ident(skill_name)} — already up to date."
        )
        return

    console.print(f"Merge complete for {fmt_ident(skill_name)}.")


def _merge_abort(ctx: ConfigContext) -> None:
    git, branch, _, skill_name = _resolve_active_merge(ctx)

    if git.is_rebasing():
        git.rebase_abort()
    elif git.is_merging():
        git.merge_abort()

    # resolve source from the merge repo, not installed.source: a cross-source
    # retarget runs the merge in X's repo while the manifest still tracks Y, so
    # Y's pinned branch is wrong (or absent) in X. Mirror `_finalize`.
    source = _source_for_repo(ctx.source_registry, git)

    target_branch = source.get_branch(git)
    if git.current_branch() != target_branch:
        git.checkout(target_branch)

    git.delete_branch(branch)

    console.print(f"Merge aborted for {fmt_ident(skill_name)}.")


def _source_for_repo(source_registry: SourceRegistry, git: GitRepo) -> Source:
    # compare by string: repo roots may be different Path implementations
    root = str(git.root)
    for name, entry in source_registry.sources.items():
        if str(entry.repo_root) == root:
            return source_registry.load_source(name)

    raise AppError(f"No registered source at {fmt_path(git.root)}.")


def _detect_merge_repo(ctx: ConfigContext) -> GitRepo:
    cwd = Path.cwd()
    candidates: list[GitRepo] = []
    for source in ctx.source_registry.sources.values():
        try:
            git = resolve_git_repo(source.repo_root)
        except AppError:
            continue

        if not _has_merge_branch(git):
            continue

        if path_within(cwd, source.repo_root):
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


def _list_merge_branches(git: GitRepo) -> list[str]:
    # broad glob captures both prefixes (`skill-merge/`, `skill-merge-keep/`); filter
    # to genuine merge branches so an unrelated `skill-merge*` branch isn't counted
    return [
        b
        for b in git.list_branches(f"{MERGE_BRANCH_STEM}*")
        if _merge_branch_prefix(b) is not None
    ]


def _has_merge_branch(git: GitRepo) -> bool:
    if _merge_branch_prefix(git.current_branch()) is not None:
        return True
    return len(_list_merge_branches(git)) > 0


def _detect_merge_branch(git: GitRepo) -> str:
    current = git.current_branch()
    if _merge_branch_prefix(current) is not None:
        return current

    branches = _list_merge_branches(git)
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
    prefix = _merge_branch_prefix(branch)
    if prefix is not None:
        parts = branch.removeprefix(prefix).split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]

    raise AppError(f"Invalid merge branch: {fmt_ident(branch)}")


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
    return source_registry.get_source_no_skills(source_name)
