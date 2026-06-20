---
id: s08t2320
slug: refactor-manual-parts-prefix-containment
status: in-review
---

# Refactor: Manual `.parts`-prefix containment in `_within` overlaps with the zip-prefix loop in `_deepest_common_ancestor

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "Manual `.parts`-prefix containment in `_within` overlaps with the zip-prefix loop in `_deepest_common_ancestor`"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/discovery.py:70 (`_within`) and :119-131 (`_deepest_common_ancestor`)
- severity: nit

Both functions reason about path containment via raw `.parts` prefix arithmetic — `_within` slices `path.parts[:len(root.parts)]` and `_deepest_common_ancestor` walks `zip(result_parts, p_parts)` counting the shared prefix. They are not identical algorithms (containment vs. longest-common-prefix), so this is incidental rather than true duplication, but a single small `_shared_prefix_len(a_parts, b_parts)` (or a `_within`-style helper expressed in terms of it) would let both read the path-parts model the same way and keep the resolved/absolute precondition documented in one place. Note this is borderline — unifying could also obscure two genuinely different intents. Routed to delayed because the reviewer flags it as incidental/borderline and it spans two functions reconciling two distinct intents — structural judgement, not an obvious local collapse the apply agent should force in place.

## Suggested fix

Introduce `def _shared_prefix_len(a: tuple[str, ...], b: tuple[str, ...]) -> int` that counts matching leading parts; express `_within` as `return _shared_prefix_len(path.parts, root.parts) == len(root.parts)` and rewrite the inner loop of `_deepest_common_ancestor` to `shared = _shared_prefix_len(result_parts, p_parts)`. Only do this if the team agrees the shared `.parts` model outweighs keeping the two intents textually separate.
