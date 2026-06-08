---
id: s10t021004
slug: autofinalize-on-clean-rebase
status: done
---

# Auto-finalize on clean rebase

**Goal:** After `--continue` is implemented, update merge start to auto-finalize when rebase completes with no conflicts. Reuse the `--continue` finalization logic (FF + copy-back + manifest + cleanup) internally. Only require `--continue` when conflicts exist.

**Decisions:** Clean rebase → auto-finalize; always tell user the outcome ("merge complete" or "conflicts, run --continue")

**Key files:** `src/repo_skills/cli/_merge.py`, tests
