---
id: s08t23
slug: bad-skills-directory-detection-on
status: in-progress
---

# Bad skills directory detection on `source init`

## Context

`skills source init` mis-detects a repo's skills directory. Two problems: (1) a freshly-initialized source with no skills is invisible in `skills status`; (2) detection wrongly falls back to an empty top-level `skills/` dir when real skills exist but are spread across the repo (e.g. `claude/skills/…` and `copilot/…`). Root cause of (2): the walk's depth cap (`_MAX_DETECT_DEPTH = 3`) clears `dirnames` before checking for `SKILL.md`, so skills at depth 3 are never found, detection returns `None`, and `init` silently creates an empty `skills/`. The tool must never assume an empty dir while skills exist, must support skills living in multiple dirs, and must let the user supply the dir list when detection is ambiguous.

## Decisions

- **Multi-dir data model** — `SourceConfig` becomes a `VersionedConfig` (`CURRENT_VERSION = 1`) with `skills_dirs: list[str]` replacing the single `skills_dir: str`. *Rejected: a `str | list[str]` union (leaves a union type everywhere); a separate `extra_dirs` field (muddies scan/merge semantics).*
- **Legacy config migration** — On load, a v0 file (`skills_dir: str`) migrates to `skills_dirs=[…]`: wrap the value, clear the legacy field, bump version, and re-save the file. Matches the established `VersionedConfig` pattern; consistent with `_provider_registry` already re-saving on read (so read-only commands like `status`/`merge` rewriting `source.json` is acceptable). *Rejected: discarding old data on OUTDATED (loses name/branch — what manifest/provider-registry do, but unacceptable here); a pure pydantic alias/validator with no version bump (user wants the versioning mechanism).*
- **Walk depth & pruning** — Drop the arbitrary depth cap entirely. Keep skipping dot-dirs; once a dir contains `SKILL.md`, record it and `dirnames.clear()` so we never descend into a skill's internals. Finds skills at any nesting depth (the glossary already promises leaf-name identity regardless of depth). *Rejected: keeping a raised cap with the `SKILL_FILE` check moved before the clear — the cap is arbitrary and already caused this bug.*
- **Three-case detection contract** — `detect_skills_dir` returns a typed result distinguishing NONE / SINGLE / AMBIGUOUS rather than overloading `None`. `init` branches: NONE (no `SKILL.md` anywhere) → create + use default `skills/` (current `.gitkeep` behavior), `skills_dirs=["skills"]`; SINGLE (deepest common ancestor below root) → auto-detect that one dir; AMBIGUOUS (common ancestor *is* the repo root, skills straddle it) → **error**, instruct user to re-run with explicit `--skills-dir`. Never guess, never assume empty while skills exist.
- **`--skills-dir` CLI flag** — Repeatable option (typer `list[str]`), e.g. `--skills-dir claude/skills --skills-dir copilot`. When ≥1 value is given, skip detection entirely and use the values verbatim (normalized to repo-relative POSIX). *Rejected: a single comma-separated value (escaping problems, less clear).*
- **Validation of explicit list** — Reject only paths that escape the repo (absolute-outside-repo or `../` traversal). Do NOT require the dir to exist or to already contain a `SKILL.md` — the first dir doubles as the merge target (`merge` creates it on demand) and a user may name dirs ahead of populating them. A soft note when a listed dir currently has no skills is fine; not fatal.
- **Multi-dir scan + collision handling** — `_collect_source_skills` scans every dir in `skills_dirs`. A skill leaf name appearing in more than one dir is a collision: introduce a dedicated `SkillNameCollisionError(AppError)` for consistent message formatting, but instead of raising it, print it inline (`[red]Error:[/red] …`, the same rendering the error handler uses) and **exclude all copies** of that name from the resolved skills. The source stays usable for its other skills across `install`/`update`/`status`. *Rejected: first-dir-wins (would make merge/update act on a dir the user didn't choose); raising/aborting (one mirrored skill would break the whole source / blank `status`).*
- **Orphan merge target** — `_merge.py` writes a merged orphan into `skills_dirs[0]` (the active dir) instead of the old single `skills_dir`. `init` guarantees a non-empty list, so no empty-list case (defensive assert is cheap).
- **Re-init reconciles `--skills-dir`** — `_handle_reinit` treats `--skills-dir` like name/branch: if the given list differs from stored `skills_dirs`, update and report the change (`dirs: [...] → [...]`). When `--skills-dir` is omitted on reinit, leave the stored list untouched and do not re-detect (matches today's behavior).
- **Status shows zero-skill sources** — Build `all_sources` from `source_registry.sources` ∪ `installed_by_source.keys()` (the latter still surfaces sources lingering in the manifest after being unregistered). A source with no installed and no available rows prints its `Source <name>` header followed by a dim `(no skills)` placeholder line, so `init` is always confirmable via `status`. (Fixes Issue #1.)
- **Remove dead detection helpers** — Delete `resolve_repo_dir` (`cli/_deps.py`) and `find_repo_skills_dir` (`discovery.py`) plus the latter's tests. Both hardcode `root / "skills"`, `resolve_repo_dir` has no callers, and `find_repo_skills_dir` is used only by that dead function — leaving them contradicts the new multi-dir model.

## Docs updated

- `CONTEXT.md` — "Skills root" replaced by "Skills dirs" (multiple dirs, detection rules, never-assume-empty) and "Active skills dir" (first dir = merge target); "Skill"/"Category" entries note the collision rule.
- `docs/adr/0005-skills-dir-detection.md` — records the list model, the refuse-to-guess detection policy (rejecting auto-detected multi-dir lists), active dir, and collision drop.

## Open questions

- None outstanding — all grill questions resolved.

## Out of scope

- Auto-detecting the multi-dir list in the ambiguous case (deliberately rejected in favor of requiring `--skills-dir`).
- Any change to how skills are identified beyond leaf-name (still leaf-name identity).
- Broader rework of `status` typing (the existing `# TODO: rework to typed structures` is untouched this round).

## Subtasks

- [~] [s08t2301](s08t2301-versioned-skillsdirs-config-legacy-migration.md): **review** Versioned skills_dirs config + legacy migration
- [~] [s08t2302](s08t2302-depthfree-detection-with-threecase-contract.md): **review** Depth-free detection with three-case contract
- [~] [s08t2303](s08t2303-source-init-branching-skillsdir-flag.md): **review** Source init branching + --skills-dir flag
- [~] [s08t2304](s08t2304-multidir-scan-collision-exclusion.md): Multi-dir scan + collision exclusion
- [~] [s08t2305](s08t2305-orphan-merge-target-active-dir.md): **review** Orphan merge target = active dir
- [ ] [s08t2306](s08t2306-status-shows-zeroskill-sources.md): Status shows zero-skill sources
- [ ] [s08t2307](s08t2307-remove-dead-detection-helpers.md): Remove dead detection helpers
- [~] [s08t2308](s08t2308-resolve-broken-source-json-handling.md): **review** Resolve broken source.json handling (duplicate message / fatal-vs-graceful)
- [~] [s08t2309](s08t2309-move-v0-migration-off-sourceconfig.md): **review** Move v0 migration off SourceConfig into a dedicated _SourceConfigV0 model
- [~] [s08t2310](s08t2310-unify-versioned-config-migration-via.md): **review** Unify versioned-config migration via a raw-dict / migrate hook on load_versioned_config
- [~] [s08t2311](s08t2311-reconsider-collapsing-broken-gt-none.md): **review** Reconsider collapsing BROKEN-&gt;None in load_source_config; expose ConfigState instead of re-stat via source_config_exists
- [~] [s08t2312](s08t2312-refactor-presence-check-abuses-full.md): **review** Refactor: Presence check abuses full detection walk (detect_skills_dir) for a yes/no answer
- [~] [s08t2313](s08t2313-refactor-repeated-kind-is-single.md): **review** Refactor: Repeated `kind is SINGLE and path is not None` guard with type-narrowing comment is a leaky DetectResult contr
- [~] [s08t2314](s08t2314-refactor-reinit-change-message-displays.md): **review** Refactor: Reinit change message displays skills_dirs sorted, hiding the active-dir order
- [~] [s08t2315](s08t2315-refactor-no-skills-note-fires.md): **review** Refactor: "no skills" note fires on a no-op reinit with an unchanged, populated-but-empty dir
- [~] [s08t2316](s08t2316-refactor-repeated-skills-dir-values.md): **review** Refactor: Repeated --skills-dir values are stored verbatim without de-duplication
- [~] [s08t2317](s08t2317-refactor-parts-prefix-path-containment.md): **review** Refactor: parts-prefix path containment logic conceptually overlaps the AMBIGUOUS equality check
- [~] [s08t2318](s08t2318-refactor-normalize-skills-dirs-mixes.md): **review** Refactor: `_normalize_skills_dirs` mixes path validation/normalization with user-facing console output
- [~] [s08t2319](s08t2319-refactor-dirs-change-line-renders.md): **review** Refactor: `dirs` change line renders a sorted list, hiding active-dir (first-element) ordering
- [~] [s08t2320](s08t2320-refactor-manual-parts-prefix-containment.md): **review** Refactor: Manual `.parts`-prefix containment in `_within` overlaps with the zip-prefix loop in `_deepest_common_ancestor
- [~] [s08t2321](s08t2321-refactor-within-prefix-check-could.md): **review** Refactor: _within prefix check could lean on stdlib is_relative_to with the symlink concern documented at the call site
- [~] [s08t2322](s08t2322-refactor-path-containment-check-duplicated.md): **review** Refactor: Path-containment check duplicated between new _within helper and _merge.py
- [~] [s08t2323](s08t2323-refactor-dir-has-skills-uses.md): **review** Refactor: _dir_has_skills uses the heavy classification walk just to ask a yes/no question
- [ ] [s08t2324](s08t2324-dedup-two-source-test-fixture.md): Dedup two-source test fixture into a helper
