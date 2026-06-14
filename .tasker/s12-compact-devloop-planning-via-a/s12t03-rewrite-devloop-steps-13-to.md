---
id: s12t03
slug: rewrite-devloop-steps-13-to
status: done
---

# Delete the /dev-tdd skill file

## Goal

Remove `~/.claude/skills/dev-tdd/SKILL.md` now that its content is folded into `/tdd` (Slice 1) and every reference has been repointed (Slice 2). Done last so deletion leaves nothing dangling.

## Decisions & constraints

- **Delete the `/dev-tdd` skill file** once `/tdd` is dual-mode-capable and no reference points at `/dev-tdd`. *Rejected: keeping it "just in case" — YAGNI; it is now a pure duplicate of content living in `/tdd`.*
- Must run **after** Slices 1 and 2 — deleting before the fold-in or before the reference migration would break callers.
- The `/tdd` skill and its sidecars (including the new `human-mode.md`) remain intact.

## Edge cases

- If the grep from Slice 2 still finds any live `/dev-tdd` reference, fix it before deleting (the file's own self-references don't count).
- Remove the `dev-tdd/` directory if it is left empty after deleting `SKILL.md`.

## Key files

- Delete: `~/.claude/skills/dev-tdd/SKILL.md` (and its now-empty directory).
- Verify clean: a final grep for `dev-tdd` across `~/.claude/skills/` and `/work/docs/agents/` returns nothing.

## Acceptance criteria

- `~/.claude/skills/dev-tdd/SKILL.md` no longer exists.
- A repo-wide grep for `dev-tdd` returns zero hits.
- `/tdd` (dual-mode) and its sidecars remain intact and functional for both human and subagent invocation.
