---
id: s08t33
slug: add-cli-orphanmerge-test-for
status: done
---

# Add CLI orphan-merge test for frontmatter-present-but-no-description

Follow-up from s08t27 (review, out-of-scope nit).

The orphan-merge commit message has two CLI-level tests in `tests/cli/test_merge.py` `TestMergeOrphan`: subject-only for a skill with NO frontmatter (`test_orphan_commit_message`), and subject+body for a skill WITH a frontmatter `description` (`test_orphan_commit_message_with_description`).

The one untested CLI permutation is frontmatter-present-but-no-`description` key (distinct from no-frontmatter at all): it should also produce a subject-only commit `feat: add `<name>` skill`. The branch is covered at the helper level (`TestReadSkillDescription.test_returns_none_when_frontmatter_has_no_description`) and the CLI wiring is identical, so this is low-value belt-and-suspenders — add a CLI test asserting the exact subject-only message for an orphan skill whose SKILL.md has frontmatter without a `description` key.
