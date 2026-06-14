---
id: s12t02
slug: add-execute-mode-to-devtdd
status: done
---

# Add execute mode to /dev-tdd

## Goal

Extend `~/.claude/skills/dev-tdd/SKILL.md` with a second mode, `mode: execute`, that drives red-green-refactor to green tests for one slice — consuming the shared digest from plan mode. An explicit `mode:` keyword dispatches between `plan` and `execute`.

## Decisions & constraints

- **`/dev-tdd` owns BOTH modes** so `/dev-loop` never calls `/tdd` at all, and every interactive-suppression hack (the current "use tdd's skip-review path" instructions) disappears. *(Rejected: `/dev-tdd` owns plan only, execute stays on `/tdd` — leaves the suppression hacks in place.)*
- **Explicit `mode:` dispatch.** The spawn prompt opens with `mode: plan` or `mode: execute`; the skill never infers mode from inputs.
- **Execute-mode inputs:** the one slice (goal + acceptance criteria), the shared **digest** (four-section), and any decisions/constraints. It consumes the digest rather than re-exploring from zero, though it may look at specifics for its own slice.
- **Green-test contract:** execute-mode returns only when tests are green; if it cannot reach green it stops and reports (never returns red as done). Behavior-preserving rules for refactor application carry over from `/tdd`.
- **Per-finding outcome reporting:** when execute-mode applies review/refactor findings, it returns `{finding, outcome: applied|dropped, reason}` per finding (this is what `/dev-loop` Steps 3d/4c consume).
- **Non-interactive**, same as plan mode: no approval waits, no `/grill-me`.
- Continues to reference `/tdd`'s craft sidecars (tracer-bullet loop, mocking-at-boundaries, deep-modules, interface-design) rather than restating them.

## Edge cases

- Cannot reach green → stop and report which slice/finding failed and why.
- A refactor finding can't stay green → drop it, report `outcome: dropped` with reason; never change expected behavior to force it through.
- Digest missing a fact the slice needs → execute-mode may inspect the codebase for that specific gap (digest is a starting point, not a hard boundary).

## Key files

- Edit: `~/.claude/skills/dev-tdd/SKILL.md` (built in the previous slice).
- Reference: `~/.claude/skills/tdd/SKILL.md` Tracer Bullet / Incremental Loop / Refactor sections; `~/.claude/skills/dev-loop/SKILL.md` Steps 3a/3d/4c for the consumption contract.

## Acceptance criteria

- The skill documents an `execute` mode dispatched by an explicit `mode:` keyword alongside `plan`.
- Execute-mode's documented inputs include the slice, the four-section digest, and decisions/constraints.
- It states the green-test contract (return only when green; stop+report otherwise) and the per-finding `{finding, outcome, reason}` return shape.
- It remains non-interactive and references (does not duplicate) the craft sidecars.
