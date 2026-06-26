---
id: s16
slug: grind
status: in-progress
---

# Grind

## Subtasks

- [~] [s16t01](s16t01-allow-to-merge-a-skill.md): **review** Allow to merge a skill to *another* skill source
- [~] [s16t02](s16t02-unify-same-source-and-cross.md): **review** Unify same-source and cross-source merge engines
- [~] [s16t03](s16t03-encode-keep-source-intent-in.md): **review** Encode keep-source intent in the merge branch name
- [ ] [s16t04](s16t04-move-repo-root-source-mapping.md): Move repo-root→source mapping onto SourceRegistry with ambiguity guard
- [ ] [s16t05](s16t05-replace-merge-engine-callbacks-with.md): Replace merge-engine callbacks with a discriminated result object
- [ ] [s16t06](s16t06-collapse-merge-engine-keep-source.md): Collapse merge-engine keep-source flags to one (contested)
- [ ] [s16t07](s16t07-add-provider-installed-path-to.md): Add Provider.installed_path() to dedupe install-path math
- [~] [s16t08](s16t08-refactor-orphaned-merge-state-json.md): **review** Refactor: Orphaned merge-state.json left on disk for upgrading users; no cleanup
- [~] [s16t09](s16t09-refactor-keep-source-early-return.md): **review** Refactor: keep-source early-return pattern repeated across three finalize sinks
- [~] [s16t10](s16t10-refactor-current-branch-or-list.md): Refactor: current-branch-or-list prefix check duplicated in _has_merge_branch and _detect_merge_branch
- [~] [s16t11](s16t11-refactor-in-progress-block-check.md): Refactor: In-progress block check re-parses branches that _list_merge_branches already validated
- [ ] [s16t12](s16t12-refactor-in-progress-block-check.md): Refactor: In-progress block check routes pre-validated branches through the raising parser
- [ ] [s16t13](s16t13-refactor-current-branch-or-list.md): Refactor: current-branch-or-list precedence probe duplicated across _has_merge_branch and _detect_merge_branch
- [ ] [s16t14](s16t14-refactor-keep-source-early-return.md): Refactor: keep-source early-return guard now truly parallel across three finalize sinks
- [ ] [s16t15](s16t15-refactor-merge-py-exceeds-the.md): Refactor: _merge.py exceeds the 1k-line module threshold
- [ ] [s16t16](s16t16-refactor-legacy-merge-state-json.md): Refactor: Legacy merge-state.json cleanup never fires for upgrading users who don't resume a merge
- [ ] [s16t17](s16t17-refactor-migration-note-deferred-keep.md): Refactor: Migration note ('deferred keep-source merges must be re-run') lives only in a code comment, not surfaced to us
- [ ] [s16t18](s16t18-refactor-twin-test-wrappers-for.md): Refactor: Twin test wrappers for legacy-state cleanup duplicate the same 6-line boilerplate
- [ ] [s16t19](s16t19-refactor-merge-py-exceeds-the.md): Refactor: _merge.py exceeds the 1k-line structural guideline (now 1301 lines)
- [ ] [s16t20](s16t20-refactor-merge-branch-prefix-is.md): Refactor: _merge_branch_prefix is a string-returning function used almost everywhere as a boolean predicate
- [ ] [s16t21](s16t21-refactor-fresh-merge-block-check.md): Refactor: Fresh-merge block check lists+parses all merge branches instead of probing the two candidate names
- [ ] [s16t22](s16t22-refactor-merged-still-tracking-now.md): Refactor: _merged_still_tracking now has a single caller — thin pass-through layer with _emit_keep_source
- [ ] [s16t23](s16t23-refactor-mid-upgrade-deferred-keep.md): Refactor: Mid-upgrade deferred --keep-source merges silently retarget the tracking source
- [ ] [s16t24](s16t24-refactor-legacy-merge-state-json.md): Refactor: Legacy merge-state.json never cleaned up for users who don't resume a merge
- [ ] [s16t25](s16t25-refactor-migration-warning-lives-only.md): Refactor: Migration warning lives only in a code comment, not surfaced to the operator
- [ ] [s16t26](s16t26-refactor-merge-py-remains-over.md): Refactor: _merge.py remains over 1000 lines after the refactor
- [ ] [s16t27](s16t27-refactor-list-merge-branches-split.md): Refactor: list-merge-branches + _split_merge_branch match repeated across _active_merge_branch_for and _detect_merge_bra
- [ ] [s16t28](s16t28-refactor-plain-prefix-mid-merge.md): Refactor: Plain-prefix mid-merge resume still inlined while keep-prefix resume is extracted
- [ ] [s16t29](s16t29-refactor-has-merge-branch-and.md): Refactor: _has_merge_branch and _detect_merge_branch both unpack _current_or_listed_merge_branches but each ignores one 
- [ ] [s16t30](s16t30-refactor-eager-branch-listing-regresses.md): Refactor: Eager branch listing regresses the current-branch fast path
- [ ] [s16t31](s16t31-refactor-current-or-listed-merge.md): Refactor: `_current_or_listed_merge_branches` always lists branches even when the current branch already answers the que
- [ ] [s16t32](s16t32-refactor-legacy-merge-state-json.md): Refactor: Legacy merge-state.json cleanup only fires on --continue/--abort, never on a fresh merge
- [ ] [s16t33](s16t33-refactor-active-merge-branch-for.md): Refactor: _active_merge_branch_for returns str | None but the sole caller only tests `is not None`
- [ ] [s16t34](s16t34-refactor-branch-naming-parsing-cluster.md): Refactor: Branch-naming/parsing cluster is a cohesive seam ripe for extraction; _merge.py sits at 1330 lines (>1k)
