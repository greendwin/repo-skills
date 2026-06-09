---
id: s08t2601
slug: distinct-now-tracked-and-in
status: done
---

# Distinct "now tracked and in sync" message on re-attach

## Goal

Running `skills merge` on a skill that gets re-attached (a previously-detached skill whose commit is reachable again) — or first-attached (a previously untracked skill gaining a baseline) — prints `"<ident> is now tracked and in sync. Nothing to merge."` and exits 0. A genuine noop (tracked, not detached, content matches baseline) still prints the existing `"<ident> is already synced. Nothing to merge."`.

## Decisions & constraints

- **Branch the in-sync message on whether a re-attach occurred.** Both in-sync code paths already compute a re-attach condition just before raising `NoopError` and call `_reattach_installed_skill`. Reuse that boolean to choose the message; do not always print "already synced".
  - Path A (`provider is not None`, content matches baseline): `reattached = installed.detached`.
  - Path B (`provider is None`, no diverged provider): `reattached = installed.detached or not installed.baseline`.
  - *Rejected: a single generic "in sync" message — keeps conflating a genuine noop with a real state change.*
- **One unified message for both sub-cases.** The state-change outcome covers re-attach (`installed.detached` was set) and first-attach (`not installed.baseline`, a previously untracked skill). `"<ident> is now tracked and in sync. Nothing to merge."` is truthful for both. *Rejected: two distinct messages keyed on `detached` — the nuance already lives in `status`; would double the branch and test matrix.*
- **Keep `NoopError` / exit 0.** A manifest mutation happened, but no merge was performed and nothing for the user to act on. Keep the `"Nothing to merge."` tail for consistency with the genuine-noop sibling message.
- **Centralize wording in a helper.** Add `_in_sync_message(skill_name: str, *, reattached: bool) -> str` returning the re-attached wording when `reattached`, else the existing "already synced" wording. Both call sites set `reattached = <their condition>`, call `_reattach_installed_skill` when `reattached`, then `raise NoopError(_in_sync_message(skill_name, reattached=reattached))`. Removes the currently-duplicated literal.

## Edge cases

- Genuine noop (non-detached, has baseline, content matches) must keep printing "already synced" — the two messages must not silently converge.
- Path A (line ~181) is only reached when `provider is not None`, i.e. `merge --from <provider>`; it is currently untested.
- First-attach via path B's `not installed.baseline` reuses the same unified message — no separate wording.

## Key files

- `src/repo_skills/cli/_merge.py` — in-sync branches at ~lines 178–186 (path A) and ~189–201 (path B); existing `_reattach_installed_skill` at ~line 311. Add `_in_sync_message` helper.
- `tests/cli/test_merge.py` — `test_reattaches_detached_skill_when_all_in_sync` (~line 601, path B), `test_reports_synced_when_no_provider_diverged` (~line 198, genuine noop).
- Output assertion helper `assert_words_in_message` (already used throughout `test_merge.py`).

## Acceptance criteria

1. `test_reattaches_detached_skill_when_all_in_sync` updated to assert the new wording — `assert_words_in_message(result.output, "tracked", "in sync")` — keeping its existing manifest assertions (`not entry.detached`, baseline rewritten to the reattach commit).
2. New path-A regression test: a detached skill merged with `--from <provider>` (so `provider is not None`) asserts the new "now tracked and in sync" message AND that `detached` is cleared and the baseline is rewritten — closing the untested branch at ~line 181.
3. `test_reports_synced_when_no_provider_diverged` kept as the genuine-noop guard, tightened to also assert the word `"already"` so the two messages can't silently converge.
4. `uv run tox` passes on all environments (fix any pre-existing issues too).
