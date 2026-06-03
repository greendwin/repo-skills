---
id: s06t1802
slug: ssource-filters-the-update-work
status: pending
---

# `-s/--source` filters the update work set

## Goal

`skills update -s agent-skills` updates only that source's installed skills. `-s` composes with a positional skill name; a named skill that doesn't belong to the source errors clearly.

## Decisions & constraints

- **`-s` and `name` compose** — both apply as filters against the collected set; mismatch (named skill not in the given source) → clear `AppError`. *Rejected: mutually-exclusive flags; silent precedence of one over the other.*
- **Error semantics** — unknown `-s` source → `AppError` "Source X not found" (reuse the registry's existing not-found error); valid source with no installed skills → `NoopError`.
- **Option spelling** — `("--source", "-s")`, mirroring `install`/`merge`.
- Filtering happens inside the collection function from the previous slice — no new branch in `update` itself.

## Edge cases

- Unknown source name.
- Valid source with zero installed skills → no-op message.
- `-s X foo` where `foo` is not from source `X` → mismatch error.

## Key files

- `src/repo_skills/cli/_update.py`
- `tests/cli/test_update.py`

## Acceptance criteria

- `-s X` narrows updates to skills from source `X`.
- Unknown source and skill/source mismatch both error with clear messages.
- Valid-but-empty source produces a `NoopError` ("No skills installed from source X").
