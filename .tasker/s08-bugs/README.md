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
- [x] [s08t18](s08t18-error-when-manifest-version-is.md): Error when manifest version is higher than supported
- [x] [s08t23](s08t23-bad-skills-directory-detection-on/): Bad skills directory detection on `source init`
- [x] [s08t25](s08t25-git-output-overwrite-update-header.md): Git output overwrite update header
- [x] [s08t26](s08t26-misleading-already-synced-message/): Misleading "already synced" message
- [x] [s08t27](s08t27-missing-provider-in-commit-message.md): Missing provider in commit message on skill merge
- [x] [s08t28](s08t28-inconsistent-new-lines-between-groups.md): Inconsistent new lines between groups
- [x] [s08t29](s08t29-windows-support/): Windows support
- [x] [s08t31](s08t31-add-newerversion-guard-to-provider.md): Add newer-version guard to provider registry loader; extract shared versioned-config loader
- [x] [s08t32](s08t32-reduce-scaffolding-duplication-in-testreadskilldescription.md): Reduce scaffolding duplication in TestReadSkillDescription
- [x] [s08t33](s08t33-add-cli-orphanmerge-test-for.md): Add CLI orphan-merge test for frontmatter-present-but-no-description
- [x] [s08t34](s08t34-relocate-skillmd-frontmatter-reader-and.md): Relocate SKILL.md frontmatter reader and dedup SKILL.md constant
- [x] [s08t35](s08t35-harden-skillmd-description-parsing-for.md): Harden SKILL.md description parsing for quoted and block-scalar values
- [x] [s08t37](s08t37-showing-outdated-even-though-its/): Showing 'outdated' even though it's up-to-date
- [ ] [s08t38](s08t38-unclear-error-on-install-failure.md): Unclear error on install failure
- [ ] [s08t39](s08t39-relax-clean-repo-guard-in.md): Relax clean-repo guard in ensure_on_branch for the no-checkout path
