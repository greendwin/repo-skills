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
- [~] [s16t09](s16t09-refactor-keep-source-early-return.md): Refactor: keep-source early-return pattern repeated across three finalize sinks
- [~] [s16t10](s16t10-refactor-current-branch-or-list.md): Refactor: current-branch-or-list prefix check duplicated in _has_merge_branch and _detect_merge_branch
- [~] [s16t11](s16t11-refactor-in-progress-block-check.md): Refactor: In-progress block check re-parses branches that _list_merge_branches already validated
- [ ] [s16t12](s16t12-refactor-in-progress-block-check.md): Refactor: In-progress block check routes pre-validated branches through the raising parser
- [ ] [s16t13](s16t13-refactor-current-branch-or-list.md): Refactor: current-branch-or-list precedence probe duplicated across _has_merge_branch and _detect_merge_branch
- [ ] [s16t14](s16t14-refactor-keep-source-early-return.md): Refactor: keep-source early-return guard now truly parallel across three finalize sinks
- [ ] [s16t15](s16t15-refactor-merge-py-exceeds-the.md): Refactor: _merge.py exceeds the 1k-line module threshold
- [ ] [s16t16](s16t16-refactor-legacy-merge-state-json.md): Refactor: Legacy merge-state.json cleanup never fires for upgrading users who don't resume a merge
- [ ] [s16t17](s16t17-refactor-migration-note-deferred-keep.md): Refactor: Migration note ('deferred keep-source merges must be re-run') lives only in a code comment, not surfaced to us
- [ ] [s16t18](s16t18-refactor-twin-test-wrappers-for.md): Refactor: Twin test wrappers for legacy-state cleanup duplicate the same 6-line boilerplate
