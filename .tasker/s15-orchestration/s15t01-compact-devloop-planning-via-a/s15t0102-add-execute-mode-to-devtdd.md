---
id: s15t0102
slug: add-execute-mode-to-devtdd
status: done
---

# Migrate every /dev-tdd reference back to /tdd

## Goal

Repoint every reference to the soon-to-be-deleted `/dev-tdd` skill back at `/tdd` (preserving `mode:` where present), so no part of the skill set names a skill that is about to be removed. One coherent change across the whole set.

## Decisions & constraints

- **Migrate all references in one change** — a dangling reference to a deleted skill is latent breakage; "one canonical `/tdd`" is defeated if half the skill set still says `/dev-tdd`.
- **Spawn mechanism unchanged; `tdd` agent stays deleted.** `/dev-loop` still spawns a `general-purpose` agent with prompt "invoke `/tdd` in `mode: {plan|execute}` …"; no dedicated wrapper. Only the skill name in spawn prompts changes (`/dev-tdd` → `/tdd`). *Rejected: re-introducing a `tdd` agent — re-creates the orphan-prone duplicate already removed.*
- Preserve `mode: plan` / `mode: execute` wording wherever it appears — only the skill name flips.
- **Grep-confirm the exact set before editing** — the list below is from the prior session and must be re-verified; catch any reference it missed.

## Edge cases

- A `/dev-tdd` mention that is actually describing the now-removed fork's history (vs. a live spawn instruction) → reword, don't leave a stale name.
- Distinguish the `/tdd` *skill* name (legitimate) from any lingering spawnable-`tdd`-*agent* reference (must not reappear).
- Leave genuine `/tdd`-skill references in `impl-loop`, `worktree-loop`, `setup-task-tracker`, `to-tasks` untouched — they already point at the right skill.

## Key files (grep-confirm first)

- `~/.claude/skills/dev-loop/SKILL.md` — roles table, invariants, Steps 2 / 3a / 3d / 4c
- `~/.claude/skills/review-iter/SKILL.md`
- `~/.claude/skills/fix-tests/SKILL.md`
- `~/.claude/skills/setup-dev-loop/SKILL.md`, `FORMAT.md`, `templates/generic.md`, `templates/claude-code.md`, `examples/dev-loop.md`
- `/work/docs/agents/dev-loop.md` (the only in-repo file)

## Acceptance criteria

- A grep for `dev-tdd` across `~/.claude/skills/` and `/work/docs/agents/` returns only the `/dev-tdd` skill file itself (removed in the next slice) — no other live reference remains.
- Every former `/dev-tdd` spawn instruction now reads `/tdd` with its `mode:` keyword intact.
- `/dev-loop`'s roles table and invariants name `/tdd` as the spawned writer/planner; no spawnable `tdd` agent is reintroduced.
- `docs/agents/dev-loop.md` (in-repo) names `/tdd` as the sole writer.
