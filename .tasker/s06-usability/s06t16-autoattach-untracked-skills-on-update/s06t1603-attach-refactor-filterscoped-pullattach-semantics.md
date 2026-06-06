---
id: s06t1603
slug: attach-refactor-filterscoped-pullattach-semantics
status: done
---

# Attach refactor + filter-scoped pull/attach semantics

## Context

Follow-up to s06t1601/s06t1602 (auto-attach untracked skills on `update`). Folds in the dev-loop's delayed refactor findings plus a new filter-semantics requirement from the user.

## Decisions

- **Auto-attach must never expand the pull set beyond the explicit filters.** Eligible attach sources:
  - **No filters** (no skill names, no `-s`): scan **all registered sources** (a zero-install source may be pulled if it has an exact untracked match). *(User choice.)*
  - **With filters**: `eligible = (sources of the collected target skills) ∪ (explicit -s sources)` — skill-name and source filters are **additive**. The pull set equals the tracked-target sources ∪ attach-candidate sources, where attach candidates are drawn only from `eligible`, so filters are never broadened by attach. `-s X` pulls/attaches only X (even with zero installed skills); name-only filters stay inert for attach (named skills are tracked).
- **D2 — name-membership candidate detection.** Decide attach candidates and the empty/no-op check by skill-**name** membership *before* pulling (local walk, no network), then hash-validate the exactly-one-source match *post-pull* at attach time. Removes the pre-pull hashing pass.
- **D1 — seam cleanup.** Carry the resolved `Source` (+ computed hashes) onto `_AttachCandidate`; drop `_load_source` (it reloads the registry from disk per candidate); remove the redundant source load + 2-3x hashing across `_matching_sources`/`_attach_skill`/`_update_skill`; have the attach step return `dict[str, InstalledSkill]` so `update()` spreads it instead of decoding a `None` sentinel. Preserve the post-pull re-validation (pull runs between candidate-finding and attach) and rework the `_load_source` monkeypatch test.
- **D3 — shared baseline helper.** Extract the commit-resolve + `verify_commit_content` + `register_skill(Baseline(...))` unit shared by `_install._record_manifest`/`_resolve_commit` and `_attach_skill`; keep the `branch` parameter and the raise-vs-return-None failure policy at the call sites.

## Out of scope

- `update` still treating detached manifest entries as tracked (not attach candidates) — intended; detached recovery owns that path.
