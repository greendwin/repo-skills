---
id: s08t3709
slug: make-the-recoveredbaselineadvance-invariant-explicit
status: pending
---

# Make the RECOVERED/baseline-advance invariant explicit in reattach carry

## Rationale

`_carry_reattached_to_latest` in `src/repo_skills/cli/_update.py` unconditionally returns `transition=_Detach.RECOVERED` with an advanced baseline. This is currently safe only because `_attempt_safe_reattach` guarantees all installed copies are byte-identical and match the found baseline's `files`, so `_decide_actions` can only yield UPDATE/UP_TO_DATE (never SKIPPED). That invariant is implicit and uncommented at the return site; if `_attempt_safe_reattach`'s "all copies identical" guard is ever loosened, this would advance the baseline over locally-modified copies and wrongly report RECOVERED.

## Suggested fix

Either assert the invariant explicitly here (e.g. assert none of the resulting statuses is SKIPPED before advancing) or compute `in_sync` from `provider_statuses` as the main body does and only report RECOVERED/advance when truly synced — failing loudly otherwise. Pin with a test installing a third provider that is locally-modified-yet-matches-fingerprint.

## Note

If F2 (de-duplicating `_carry_reattached_to_latest` into the shared in_sync path) lands first, this invariant may be naturally satisfied by reusing the main body's `in_sync` computation — re-evaluate whether a standalone fix is still needed.
