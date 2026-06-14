---
id: s12t04
slug: delete-the-orphaned-tdd-agent
status: done
---

# Delete the orphaned tdd agent wrapper

## Goal

Remove `~/.claude/agents/tdd.md` and ensure nothing left in the skill set references a spawnable `tdd` agent.

## Decisions & constraints

- The `tdd` agent wrapper existed **solely** so `/dev-loop` could spawn it; after the rewrite (previous slice) dev-loop spawns `general-purpose` + `/dev-tdd` instead, so the wrapper is orphaned. *(Rejected: keeping it "just in case" — YAGNI; it merely duplicates the `/tdd` skill. Re-create if a real future need arises.)*
- The `/tdd` **skill** is untouched and stays available for direct human invocation; only the **agent** wrapper is deleted.
- Do this LAST, after Slice 3 has stopped referencing the `tdd` agent, so deletion leaves no dangling reference.

## Edge cases

- A lingering mention of the `tdd` agent in `/dev-loop` or `docs/agents/dev-loop.md` after the rewrite → scrub it (the rewrite slice should have already, but verify).

## Key files

- Delete: `~/.claude/agents/tdd.md`
- Verify clean: `~/.claude/skills/dev-loop/SKILL.md`, `docs/agents/dev-loop.md`, and any other agent/skill text mentioning a `tdd` agent (vs. the `/tdd` skill, which is fine).

## Acceptance criteria

- `~/.claude/agents/tdd.md` no longer exists.
- No remaining reference points at a spawnable `tdd` agent in dev-loop or its config.
- The `/tdd` skill and its sidecars remain intact and unmodified.
