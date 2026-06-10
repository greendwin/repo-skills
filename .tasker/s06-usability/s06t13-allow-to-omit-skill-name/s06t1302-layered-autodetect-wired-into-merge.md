---
id: s06t1302
slug: layered-autodetect-wired-into-merge
status: pending
---

# Layered auto-detect wired into merge

## Goal

Make bare `skills merge` (no skill name) auto-detect the skill to merge via the layered cascade and proceed to merge it end-to-end, printing a one-line notice of what it picked.

## Decisions & constraints

- **Layered cascade** — scan candidate buckets in precedence order `modified` -> `mergeable` -> `orphan`, using the shared classifier from Slice 1. First non-empty layer decides: exactly one candidate -> pick it; more than one -> error and stop (no fall-through); zero -> fall through to the next layer.
- **Count distinct skill names**, not (skill, provider) pairs — a skill modified under two providers is one candidate. Auto-detect resolves only the skill *name*. *Rejected: counting pairs (false ambiguity).*
- **Provider resolution unchanged** — after the name is chosen, existing resolution runs as today; if the picked skill is modified in multiple providers without `--from`, `_resolve_diverged_provider` still raises its "use --from" error. *Rejected: silently picking first provider.*
- **`--from`/`--source` narrow the scan** — when given, filter which candidates the layers consider (e.g. `--from claude` only counts skills pending under claude). *Rejected: pass-through only.*
- **Announce the pick** — before proceeding, print one line e.g. `Auto-detected modified skill grill-me.` (via `fmt_ident`), naming the layer that matched.

Note: the ambiguous-layer and nothing-to-merge error wording, and the in-progress-merge short-circuit, are handled in the sibling "Guards & error wording" slice. This slice focuses on the happy path (exactly-one in some layer -> merge succeeds).

## Edge cases

- One modified skill across two providers -> single candidate; merge proceeds, hitting existing multi-provider `--from` error only if both diverged.
- Zero modified but one mergeable -> falls through and picks the mergeable.
- `--from`/`--source` reduces a would-be-ambiguous set down to one.

## Key files

- `src/repo_skills/cli/_merge.py` (the `merge` command + `_merge_start`; replace the `skill_name is None` branch)
- shared classifier module from Slice 1
- `tests/cli/test_merge.py` (use `assert_invoke`)

## Acceptance criteria

- Bare `skills merge` with exactly one modified skill merges it and prints the auto-detect notice.
- Bare `skills merge` with zero modified but one mergeable picks the mergeable; likewise orphan when both prior layers empty.
- `--from`/`--source` narrow detection as specified.
- A single modified skill present under multiple providers is treated as one candidate.
- `uv run tox` passes (all environments).
