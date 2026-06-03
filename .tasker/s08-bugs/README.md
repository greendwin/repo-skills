---
id: s08
slug: bugs
status: pending
---

# Bugs

Fix TODO-documented bugs and issues across the CLI.

## Subtasks

- [x] [s08t01](s08t01-fix-detectmergerepo-use-cwd-source.md): Fix _detect_merge_repo: use CWD source or scan all sources
- [x] [s08t02](s08t02-fix-silent-exception-swallowing-in.md): Fix silent exception swallowing in commit matching
- [x] [s08t03](s08t03-autoswitch-to-pinned-branch-extract.md): Auto-switch to pinned branch (extract ensure_on_branch helper)
- [x] [s08t04](s08t04-remove-mergeinprogress-blocking-check.md): Remove merge-in-progress blocking check
- [x] [s08t05](s08t05-add-force-to-source-remove.md): Add --force to `source remove` (orphan installed skills)
- [x] [s08t06](s08t06-show-broken-sources-with-broken.md): Show broken sources with (broken) label in status output
- [x] ~~[s08t07](s08t07-delete-resolvedstale-todo-comments.md): Delete resolved/stale TODO comments~~
- [x] [s08t08](s08t08-add-tests-for-source-list.md): Add tests for `source list` edge cases: (missing) and (not-inited)
- [x] [s08t09](s08t09-add-tests-for-broken-source.md): Add tests for broken source display in status output
- [x] [s08t10](s08t10-detect-ambiguity-in-merge-skill.md): Detect ambiguity in merge skill resolution (sources + providers)
- [x] [s08t11](s08t11-reattach-detached-skill-on-insync.md): Reattach detached skill on in-sync, no-from merge path
- [x] [s08t12](s08t12-harden-resolvebasecommit-messaging-add-subfolder.md): Harden _resolve_base_commit messaging + add subfolder test
- [x] [s08t13](s08t13-extract-shared-setup-in-testresolvebasecommit.md): Extract shared setup in TestResolveBaseCommit
- [x] [s08t14](s08t14-broken-manifest-should-not-fail.md): Broken manifest should not fail
- [x] [s08t15](s08t15-wrong-base-commit-is-taken/): Wrong base commit is taken
- [x] [s08t16](s08t16-status-report-synced-for-outdated/): Status report 'synced' for outdated install
- [x] [s08t17](s08t17-git-fails-when-nothing-to/): Git fails when nothing to merge
- [ ] [s08t18](s08t18-error-when-manifest-version-is.md): Error when manifest version is higher than supported
- [ ] s08t19: Make sure that 'skill update' don't touch in-merge skills, show also 'status' for such skills
- [ ] s08t20: Use 'feat' prefix when merging orphan branch and 'ref' when updating existing one
