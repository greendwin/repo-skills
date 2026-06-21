---
id: s15t03
slug: grind-story-raise-review-caps
status: in-progress
---

# Grind-story: raise review caps and add refactor-first grouped pick

## Context

`grind-story` (the autonomous per-story Workflow at `.claude/workflows/grind-story.js`) currently picks exactly one pending subtask per iteration in natural order, and shares a single round cap (`CAP = 5`) across the Review-A fix-now loop, the Refactor-B apply-now loop, and the Verify tox-fix loop. We want two improvements: (1) give the two review-phase convergence loops more room before they fail, and (2) make the picker drain refactor side-tasks ahead of original feature subtasks — batching small behavior-preserving refactors into one pass — so new feature work lands on already-refactored code.

## Decisions

- **Raise the review-loop cap to 10, keep verify at 5** — both review-phase convergence loops (Review-A's fix-now loop and Refactor-B's apply-now loop) get a dedicated `REVIEW_CAP = 10`; the Verify tox-fix loop keeps `CAP = 5`. *Rejected: bumping the single shared `CAP` to 10 for all three loops — verify gating has different convergence semantics and shouldn't be loosened.*

- **"Refactoring task" reuses the existing side-task marker** — a refactoring task is any task whose description carries the `## Refactor side-task` marker block (the existing `parseDepthMarker` / depth ≥ 1 notion). *Rejected: a second, parallel human-set classification — would duplicate the depth machinery.*

- **Pick prefers refactor tasks over feature tasks** — among eligible pending subtasks, marker-bearing refactor tasks are selected before depth-0 feature subtasks, so the run drains refactors first and feature work lands on refactored code.

- **Grouping is refactor-only** — refactor tasks may be batched up to 5 per iteration; original depth-0 feature subtasks stay strictly one-per-iteration (they are tracer-bullet units with distinct acceptance criteria and must not be merged).

- **Pick agent judges feasible work size** — there is no reliable mechanical size signal before code is written, so the pick agent judges from each side-task's description (title/location/severity/suggested-fix/rationale), bundling small, local, non-overlapping refactors and stopping when the combined change looks too big to land+review in one pass, hard-capped at 5. *Rejected: a mechanical "always take next 5" rule, and severity-based gating — neither captures conflict/size.*

- **Uniform pick return shape** — pick returns `{ done, kind: 'refactor'|'feature', items: [{taskId, title, description, isStory}] }`; feature picks carry exactly one item, refactor picks 1–5. Pick atomically moves **every** returned item to in-progress before returning, so a mid-run crash leaves consistent tracker state. The loop body branches on `kind`. *Rejected: keeping the single-task fields plus an optional group array — forces a single/plural split everywhere downstream.*

- **A group is one shared pass and one commit** — a single apply agent applies all N refactorings together; Review-A / Refactor-B / Verify run once over the combined diff; one commit covers the group (no task ids in the message, per CLAUDE.md). This amortizes one review/verify cycle across N small refactors. *Rejected: picking the group together but still running the full pipeline + separate commit per member — defeats the point of batching.*

- **Refactor groups use a behavior-preserving group-apply prompt** — a group-aware variant of Refactor-B's `applyPrompt`: apply all N keeping existing tests green, never write new behavior tests, return per-member `applied|dropped` results, drop any member that can't stay green. *Rejected: reusing the feature `implementPrompt` (acceptance-criteria TDD) — refactors are behavior-preserving by construction and a bad member should drop without failing the batch.*

- **Refactor groups run the full pipeline** — apply → Review-A → Refactor-B → file-side-tasks → Verify → commit, relying on `maxDepth` to bound refactor-of-refactor recursion (Review-A stays the correctness safety net). *Rejected: a slimmed apply→Review-A→Verify pass that skips Refactor-B/file-side-tasks.*

- **Side-tasks filed from a group use MIN member depth** — the depth-suppression gate and the filed child's birth depth both use `min(member depths)` (the more permissive choice that allows deeper recursion within `maxDepth`). The child's `origin:` line lists **all** member ids joined (e.g. `s08t03+s08t05`), and that joined string feeds `findingSignature` for dedupe, since a combined-diff finding can't be pinned to one member. *Rejected: max-depth gate; per-member re-runs of Refactor-B — defeats single-pass batching.*

- **Dropped refactor tasks are cancelled in tasker** — a refactor task that is discarded must be moved to tasker's cancelled state (`mcp__tasker__cancel_task`), not merely reset. Two drop scenarios:
  - *Whole-group convergence failure* (apply can't converge, Review-A fix-now still open at cap, or tox red at cap): `git reset --hard` discards the combined change (reverting the in-progress `.tasker` edits), then cancel every member, then make a **dedicated cancellation commit** (e.g. `chore: cancel non-converging refactor side-tasks`) so the cancelled status survives and never leaks into an unrelated next item's commit. Continue with the next pick.
  - *Single member dropped within an otherwise-green group*: cancel that member **before** the group commit so its `.tasker` edit rides in the normal group commit.

- **All-members-dropped short-circuit** — if the apply step drops every member (empty refactor diff), skip Review-A/Refactor-B/Verify entirely, cancel all members, record the dedicated cancellation commit, and continue.

- **One processed report row per task** — each group member gets its own `processed` row sharing the single commit sha, so per-task origin/provenance still shows individually. *Rejected: collapsing the group into one merged report line.*

- **Feature-task failure semantics unchanged** — feature subtasks are depth 0, so a convergence failure still **Halts** the run (leaving the tree dirty for inspection); only refactor tasks are dropped+cancelled.

## Open questions

- None outstanding from the grill.

## Out of scope

- Changing the Verify tox-fix loop cap (stays 5).
- Salvage/bisect of a failed refactor group (whole group is dropped wholesale).
- Any change to feature-subtask processing beyond the new pick ordering/grouping (feature tasks remain one-per-iteration, full pipeline, Halt-on-failure).
- Changing `maxDepth` / `totalCap` defaults or their override parsing.

## Subtasks

- [~] [s15t0301](s15t0301-split-the-review-loop-cap.md): **review** Split the review-loop cap from the verify cap
- [~] [s15t0302](s15t0302-refactor-first-uniform-pick-contract.md): **review** Refactor-first, uniform pick contract (single-item groups)
- [~] [s15t0303](s15t0303-batched-refactor-pick-group-up.md): **review** Batched refactor pick (group up to 5)
- [ ] [s15t0304](s15t0304-one-pass-group-execution-apply.md): One-pass group execution: apply + single commit
- [ ] [s15t0305](s15t0305-drop-cancel-semantics-for-refactor.md): Drop/cancel semantics for refactor tasks
- [ ] [s15t0306](s15t0306-refactor-round-loop-with-cap.md): Refactor: round-loop-with-cap-break skeleton duplicated across three phases
- [ ] [s15t0307](s15t0307-refactor-reviewphasea-and-refactorphaseb-duplicate.md): Refactor: reviewPhaseA and refactorPhaseB duplicate the entire lens-round/triage/cap-break loop skeleton
- [ ] [s15t0308](s15t0308-refactor-extractfunction-helper-and-source.md): Refactor: extractFunction helper and source-loading preamble duplicated verbatim across the two .test.mjs suites
- [ ] [s15t0309](s15t0309-refactor-extractfunction-brace-walker-is.md): Refactor: extractFunction brace-walker is a fragile test seam (no string/comment awareness)
- [ ] [s15t0310](s15t0310-refactor-verify-cap-review-cap.md): Refactor: VERIFY_CAP / REVIEW_CAP split lands with no test asserting the new caps
- [ ] [s15t0311](s15t0311-refactor-normalizepick-test-asserts-shape.md): Refactor: normalizePick test asserts shape but not the documented 'one-element in this slice' invariant for multi-item i
- [ ] [s15t0312](s15t0312-refactor-normalizepick-can-silently-strip.md): Refactor: normalizePick can silently strip an item the pick agent already moved to in-progress, leaving a task stranded
- [ ] [s15t0313](s15t0313-refactor-repeat-guard-backstop-runs.md): Refactor: Repeat-guard backstop runs after the pick agent has already moved the re-served task to in-progress
- [ ] [s15t0314](s15t0314-refactor-for-const-item-of.md): Refactor: `for (const item of pick.items) await processItem(item)` comment overclaims correctness for future multi-item 
- [ ] [s15t0315](s15t0315-refactor-missing-description-items-silently.md): Refactor: Missing-`description` items silently degrade a refactor pick to depth-0 feature processing
- [ ] [s15t0316](s15t0316-refactor-top-level-js-suite.md): Refactor: Top-level JS suite test cannot detect a missing per-behavior suite (weak coverage guard)
- [ ] [s15t0317](s15t0317-refactor-pick-schema-carries-a.md): Refactor: PICK_SCHEMA carries a `kind` field with no consumer (scaffolding ahead of its slice)
- [ ] [s15t0318](s15t0318-refactor-grind-story-js-has.md): Refactor: grind-story.js has crossed the 1k-line threshold the lens flags
- [ ] [s15t0319](s15t0319-refactor-firstrepeat-recordseen-are-thin.md): Refactor: firstRepeat / recordSeen are thin identity wrappers over one-line Set operations
- [ ] [s15t0320](s15t0320-refactor-kind-is-a-dead.md): Refactor: `kind` is a dead/speculative field threaded through the whole pick contract but never consumed
- [ ] [s15t0321](s15t0321-refactor-grind-story-js-has.md): Refactor: grind-story.js has grown past 1k lines and the new per-item pipeline makes a module split natural
- [ ] [s15t0322](s15t0322-refactor-skipitem-caught-outside-the.md): Refactor: SkipItem caught outside the per-item loop silently abandons the rest of a (future) group
- [ ] [s15t0323](s15t0323-refactor-kind-is-a-dead.md): Refactor: `kind` is a dead contract field — classification duplicated between the pick agent and `resolveMarker`
- [ ] [s15t0324](s15t0324-refactor-grind-story-js-continues.md): Refactor: grind-story.js continues to grow past the 1k-line threshold (1100 -> 1185)
- [ ] [s15t0325](s15t0325-refactor-firstrepeat-recordseen-are-two.md): Refactor: firstRepeat / recordSeen are two identity-thin helpers that always travel as a pair
