from __future__ import annotations

import difflib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, NamedTuple, NoReturn, Optional

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
from repo_skills.errors import (
    AppError,
    ConfigBrokenError,
    FileNotInCommitError,
    NoopError,
)
from repo_skills.git import GitRepo, ensure_on_branch
from repo_skills.utils import (
    hash_content,
    load_raw_config,
    normalize_line_endings,
    overwrite_dir,
)

from ._app import app
from ._deps import prepare_source_repo, resolve_git_repo

# Deferred --keep-source intent rides in the keep-prefixed branch *name*, so a
# resumed `--continue` derives it from the branch — no persisted state.
# (`--abort` just deletes the branch regardless of keep-source.)
MERGE_BRANCH_STEM = "skill-merge"
MERGE_BRANCH_PREFIX = f"{MERGE_BRANCH_STEM}/"
MERGE_KEEP_BRANCH_PREFIX = f"{MERGE_BRANCH_STEM}-keep/"
_MERGE_PREFIXES = (MERGE_KEEP_BRANCH_PREFIX, MERGE_BRANCH_PREFIX)

# retired keep-source persistence artifact; see module note
LEGACY_MERGE_STATE_FILE = "merge-state.json"
_LEGACY_KEEP_SOURCE_KEY = "keep_source"


def _branch_has_legacy_keep_intent(branch: str) -> bool:
    # pre-upgrade build persisted deferred --keep-source intent here as a list of
    # plain-prefixed branch names; intent now rides the keep-prefixed branch name.
    # legacy schema (the deleted _MergeStateConfig, version 1):
    #   {"version": 1, "keep_source": [<branch>, ...]}
    # Read via the shared loader but swallow its errors: a missing/corrupt/
    # pre-upgrade artifact yields no keep intent rather than raising.
    try:
        data = load_raw_config(default_config_path(LEGACY_MERGE_STATE_FILE))
    except ConfigBrokenError:
        return False
    if data is None:
        return False
    branches = data.get(_LEGACY_KEEP_SOURCE_KEY)
    return isinstance(branches, list) and branch in branches


def _cleanup_legacy_merge_state() -> None:
    # best-effort unlink stale artifact on resume
    default_config_path(LEGACY_MERGE_STATE_FILE).unlink(missing_ok=True)


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


def _branch_is_keep_source(branch: str) -> bool:
    # decode side of _merge_branch_name's keep<->prefix mapping
    return _merge_branch_prefix(branch) == MERGE_KEEP_BRANCH_PREFIX


def _emit_keep_source(
    skill_name: str, target_name: str, old_source: str | None
) -> None:
    # single keep-source sink: content landed in target, manifest left untouched.
    # old_source None (entry vanished mid-merge) => no tracking suffix.
    tracking = (
        f" (still tracking {fmt_ident(old_source)})" if old_source is not None else ""
    )
    console.print(
        f"Merged {fmt_ident(skill_name)} into {fmt_ident(target_name)}{tracking}."
    )


def _register_and_save(
    manifest: SkillManifest,
    skill_name: str,
    *,
    source_name: str,
    baseline: Baseline | None,
) -> InstalledSkill:
    # baseline-write invariant: every register must be followed by a save.
    installed = manifest.register_skill(
        skill_name, source_name=source_name, baseline=baseline
    )
    save_skill_manifest(manifest)
    return installed


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
        _checkout_if_needed(git, target_branch)
        git.fast_forward(branch_name)

    overwrite_dir(src, dst)
    git.delete_branch(branch_name)


def _join_idents(names: Iterable[str]) -> str:
    # sorted, green-styled, comma-joined identifier list (ADR-0001)
    return ", ".join(fmt_ident(n) for n in sorted(names))


def _raise_ambiguous(
    noun: str,
    skill_name: str,
    names: Iterable[str],
    *,
    opt: str,
    verb: str = "have",
) -> NoReturn:
    # unify the "Multiple <noun> <verb> <skill> (<names>)" ambiguity raise (ADR-0001)
    raise AppError(
        f"Multiple {noun} {verb} {fmt_ident(skill_name)} ({_join_idents(names)}).",
        hint=f"Use {fmt_command(opt)} to specify.",
    )


def _retarget_suffix(target_name: str, old_source: str) -> str:
    # canonical tracking-change fragment; ADR-0001 green identifiers
    return f"now tracking {fmt_ident(target_name)} (was {fmt_ident(old_source)})"


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
        _emit_keep_source(skill_name, target_name, old_source)
        return

    commit = git.get_skill_commit(rel_path)
    _register_and_save(
        ctx.manifest,
        skill_name,
        source_name=target_name,
        baseline=make_baseline(commit, content_dir),
    )

    console.print(
        f"Retargeted {fmt_ident(skill_name)}: "
        f"{_retarget_suffix(target_name, old_source)}."
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
    # block on either prefix: a stale keep/plain branch for this skill (not just
    # branch_name's exact prefix) must not be re-merged.
    if _has_active_merge_for(git, provider.name, skill_name):
        raise AppError(
            f"Merge already in progress for {fmt_ident(skill_name)}.",
            hint=f"Run {fmt_command('skills merge --continue')} to finish active merge "
            f"or {fmt_command('skills merge --abort')} to start over.",
        )

    installed_path = provider.installed_path(skill_name)

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
        kind = "Merge" if use_merge else "Rebase"
        console.print(f"[yellow]Warning:[/yellow] {kind} has conflicts.\n")
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
        installed = _register_and_save(
            ctx.manifest,
            skill_name,
            source_name=untracked.source.name,
            baseline=None,
        )

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
        current_hashes = compute_file_hashes(provider.installed_path(skill_name))
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

    installed_path = provider.installed_path(skill_name)

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

    installed_path = provider.installed_path(skill_name)

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


_UPDATE_HINT = f"Run {fmt_command('skills update')} to pull the latest changes."


def _emit_previous_version(body: str) -> None:
    # shared not-latest tail: previous-version body + the `skills update` prompt
    console.print(f"{body}\n{_UPDATE_HINT}")


def _register_in_sync_baseline(
    manifest: SkillManifest,
    git: GitRepo,
    *,
    skill: SourceSkill,
    source_name: str,
    base_commit: str,
    installed_path: Path,
) -> bool:
    # register the in-sync baseline; return whether base_commit is the skill's tip
    # (False => matched a previous version, caller prompts `skills update`).
    _register_and_save(
        manifest,
        skill.name,
        source_name=source_name,
        baseline=make_baseline(base_commit, installed_path),
    )
    return base_commit == git.get_skill_commit(skill.rel_path)


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
        _emit_keep_source(skill.name, target.name, old_source)
        return

    is_latest = _register_in_sync_baseline(
        ctx.manifest,
        git,
        skill=skill,
        source_name=target.name,
        base_commit=base_commit,
        installed_path=installed_path,
    )

    # if the matched commit is not X's tip, warn it is a previous version instead
    # of claiming a clean "already matches".
    if not is_latest:
        _emit_previous_version(
            f"{fmt_ident(skill.name)} matches a previous version of"
            f" {fmt_ident(target.name)} — {_retarget_suffix(target.name, old_source)}."
        )
        return

    console.print(
        f"{fmt_ident(skill.name)} already matches {fmt_ident(target.name)}"
        f" — {_retarget_suffix(target.name, old_source)}."
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
        installed_path=provider.installed_path(skill_name),
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
    *,
    source: Source,
    skill: SourceSkill,
    base_commit: str,
    installed_path: Path,
) -> None:
    is_latest = _register_in_sync_baseline(
        ctx.manifest,
        git,
        skill=skill,
        source_name=source.name,
        base_commit=base_commit,
        installed_path=installed_path,
    )
    if is_latest:
        console.print(f"{fmt_ident(skill.name)} is already up to date.")
        return

    _emit_previous_version(f"{fmt_ident(skill.name)} matches a previous version.")


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
    _register_and_save(
        manifest,
        skill.name,
        source_name=source.name,
        baseline=baseline,
    )


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
        _raise_ambiguous(
            "sources", skill_name, (s.name for s, _ in matches), opt="--source"
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
        installed_path=provider.installed_path(skill_name),
        skill_name=skill_name,
        no_commit=no_commit,
    )
    if not added.committed:
        return

    commit = repo.git.get_skill_commit(added.skill_rel_path)

    manifest = load_skill_manifest()
    _register_and_save(
        manifest,
        skill_name,
        source_name=source.name,
        baseline=make_baseline(commit, added.skill_dst),
    )

    console.print(f"Merge complete for {fmt_ident(skill_name)}.")


def _find_skill_in_provider(
    provider_registry: ProviderRegistry, provider: Provider | None, skill_name: str
) -> Provider:
    if provider:
        skill_path = provider.installed_path(skill_name)
        if not skill_path.is_dir():
            raise AppError(
                f"Skill {fmt_ident(skill_name)} is not installed "
                f"in {fmt_ident(provider.name)}."
            )

        return provider

    matches = []
    for prov in provider_registry.providers:
        skill_path = prov.installed_path(skill_name)
        if skill_path.is_dir():
            matches.append(prov)

    if len(matches) > 1:
        _raise_ambiguous(
            "providers", skill_name, (p.name for p in matches), opt="--from"
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
        installed_path = provider.installed_path(skill_name)
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
        _raise_ambiguous(
            "providers",
            skill_name,
            (p.name for p in diverged),
            opt="--from",
            verb="have modified",
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


class _ActiveMerge(NamedTuple):
    git: GitRepo
    branch: str
    provider_name: str
    skill_name: str


def _resolve_active_merge(ctx: ConfigContext) -> _ActiveMerge:
    # side-effect-free locator for the in-progress merge's repo/branch/skill.
    # guard+cleanup ordering lives in _merge_continue / _merge_abort, not here.
    git = _detect_merge_repo(ctx)
    branch = _detect_merge_branch(git)
    parsed = _split_merge_branch(branch)
    if parsed is None:
        # prefix matched (else _detect_merge_branch skips it) but no skill segment
        raise AppError(
            f"Merge branch {fmt_ident(branch)} has no skill name.",
            hint=f"Run {fmt_command('skills merge --abort')} to clear it.",
        )
    provider_name, skill_name = parsed
    return _ActiveMerge(git, branch, provider_name, skill_name)


def _consume_active_merge(ctx: ConfigContext, *, guard_legacy: bool) -> _ActiveMerge:
    # resolve the in-flight merge, then clear legacy state. continue guards a
    # deferred --keep-source resume BEFORE the unlink so a refusal leaves the
    # legacy file for a later --abort; abort intentionally skips the guard.
    active = _resolve_active_merge(ctx)
    if guard_legacy:
        _guard_legacy_keep_source(active.branch)
    _cleanup_legacy_merge_state()
    return active


def _guard_legacy_keep_source(branch: str) -> None:
    # pre-upgrade deferred --keep-source: intent in merge-state.json, not the branch
    # name -> finalize would retarget (opposite of request). Refuse; --abort clears
    # state for re-run. Best-effort: only fires while the legacy file exists.
    if _branch_has_legacy_keep_intent(branch):
        raise AppError(
            f"In-flight merge {fmt_ident(branch)} was deferred with"
            f" {fmt_command('--keep-source')} before an upgrade and cannot be"
            " resumed safely.",
            hint=f"Run {fmt_command('skills merge --abort')}, then re-run with"
            f" {fmt_command('--keep-source')}.",
        )


def _merge_continue(ctx: ConfigContext) -> None:
    active = _consume_active_merge(ctx, guard_legacy=True)
    git = active.git

    if git.is_rebasing():
        git.rebase_continue()
    # an in-progress merge legitimately leaves the tree dirty
    elif not git.is_merging() and not git.is_clean():
        raise AppError(
            "Repo has uncommitted changes.",
            props={"repo": fmt_path(git.root)},
        )

    provider = ctx.provider_registry.require(active.provider_name)
    _finalize(
        ctx,
        git,
        provider,
        active.skill_name,
        merge_branch=active.branch,
        # resume path: ff/cleanup handled here, not a merge-vs-rebase signal
        already_merged=False,
    )


def _finalize(
    ctx: ConfigContext,
    git: GitRepo,
    provider: Provider,
    skill_name: str,
    *,
    merge_branch: str,
    already_merged: bool,
) -> None:
    # keep-source intent derived from branch prefix (see module note)
    keep_source = _branch_is_keep_source(merge_branch)

    source, target_branch = _resolve_merge_target(ctx.source_registry, git)
    skill = source.get_skill(skill_name)

    installed_path = provider.installed_path(skill_name)

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
        # prev gone mid-merge => nothing to keep tracking
        old_source = prev.source if prev is not None else None
        _emit_keep_source(skill_name, source.name, old_source)
        return

    new_hashes = compute_file_hashes(installed_path)

    # "already up to date" only applies to a same-source resume; a cross-source
    # retarget always changes the tracking source, so it never reads as a no-op.
    is_equal = (
        prev is not None and prev.source == source.name and prev.match_files(new_hashes)
    )

    _register_and_save(
        ctx.manifest,
        skill_name,
        source_name=source.name,
        baseline=Baseline(
            # note: take latest commit for code, since we just finished
            #       merging and must be in sync
            commit=git.get_skill_commit(skill.rel_path),
            files=new_hashes,
        ),
    )

    if is_equal:
        console.print(
            f"Nothing to merge for {fmt_ident(skill_name)} — already up to date."
        )
        return

    console.print(f"Merge complete for {fmt_ident(skill_name)}.")


def _merge_abort(ctx: ConfigContext) -> None:
    active = _consume_active_merge(ctx, guard_legacy=False)
    git = active.git

    if git.is_rebasing():
        git.rebase_abort()
    elif git.is_merging():
        git.merge_abort()

    _, target_branch = _resolve_merge_target(ctx.source_registry, git)
    _checkout_if_needed(git, target_branch)

    git.delete_branch(active.branch)

    console.print(f"Merge aborted for {fmt_ident(active.skill_name)}.")


def _checkout_if_needed(git: GitRepo, branch: str) -> None:
    # park the repo back on its pinned branch (no-op if already there)
    if git.current_branch() != branch:
        git.checkout(branch)


def _resolve_merge_target(
    source_registry: SourceRegistry, git: GitRepo
) -> tuple[Source, str]:
    # canonical "where does this merge land": cross-source source + its pinned branch.
    # derive source from the repo holding the merge branch, not installed.source:
    # a cross-source retarget runs the merge in X's repo while the manifest still
    # tracks Y, so installed.source (Y) is wrong — Y's pinned branch is absent in
    # X and resuming via Y would corrupt the entry.
    source = source_registry.source_for_repo_root(git.root)
    return source, source.get_branch(git)


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
        names = _join_idents(str(g.root) for g in candidates)
        raise AppError(
            f"Multiple source repos have merge branches ({names}).",
            hint="Run from within the target source repo.",
        )

    return candidates[0]


def _list_merge_branches(git: GitRepo) -> list[str]:
    # glob is a coarse prefilter; the prefix lookup is the real guard
    # (excludes e.g. skill-mergeable/*)
    return [
        b
        for b in git.list_branches(f"{MERGE_BRANCH_STEM}*")
        if _merge_branch_prefix(b) is not None
    ]


def _has_active_merge_for(git: GitRepo, provider_name: str, skill_name: str) -> bool:
    # prefix-agnostic: a stale keep/plain merge branch for this skill blocks a re-merge.
    # _split_merge_branch drops malformed names (no /<skill> segment)
    return any(
        _split_merge_branch(b) == (provider_name, skill_name)
        for b in _list_merge_branches(git)
    )


def _current_merge_branch(git: GitRepo) -> str | None:
    # current branch when it's a merge branch, else None — lets the common
    # resume case skip the git branch --list shell.
    current = git.current_branch()
    return current if _merge_branch_prefix(current) is not None else None


def _has_merge_branch(git: GitRepo) -> bool:
    # current-first still short-circuits the list shell
    return _current_merge_branch(git) is not None or bool(_list_merge_branches(git))


def _detect_merge_branch(git: GitRepo) -> str:
    if (current := _current_merge_branch(git)) is not None:
        return current

    branches = _list_merge_branches(git)
    if len(branches) == 1:
        return branches[0]

    if len(branches) > 1:
        names = _join_idents(branches)
        raise AppError(
            f"Multiple merge branches found ({names}).",
            hint="Checkout the one to continue.",
        )

    raise AppError(
        "No merge branch found.",
        hint=f"Run {fmt_command('skills merge')} first.",
    )


def _split_merge_branch(branch: str) -> tuple[str, str] | None:
    # strip prefix + 2-part split; None on a malformed name
    prefix = _merge_branch_prefix(branch)
    if prefix is not None:
        parts = branch.removeprefix(prefix).split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return None


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
        names = _join_idents(source_registry.sources.keys())
        raise AppError(
            f"Multiple sources registered ({names}).",
            hint=f"Use {fmt_command('--source')} to specify.",
        )

    source_name = list(source_registry.sources)[0]
    return source_registry.get_source_no_skills(source_name)
