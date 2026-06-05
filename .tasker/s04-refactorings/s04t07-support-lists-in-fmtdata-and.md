---
id: s04t07
slug: support-lists-in-fmtdata-and
status: pending
---

# Support lists in fmt_data and fmt_ident console helpers

## Goal

Let the `fmt_data` and `fmt_ident` console helpers (in `src/repo_skills/console.py`) accept a list/iterable of values, sorting and joining them automatically under the hood. This removes the need for ad-hoc join helpers at call sites.

## Motivation

`src/repo_skills/cli/_update.py` grew a local `_fmt_sources(sources)` helper that just does `", ".join(fmt_data(s) for s in sources)` to render multiple source names in the `update` command's messages. That join+format logic belongs inside the formatting helpers, not duplicated per call site.

## Scope

- Extend `fmt_data` (and `fmt_ident`) to accept either a single scalar (current behavior, unchanged) or an iterable of values. For an iterable: sort the items, format each, and join with `", "`.
- Replace the `_fmt_sources` helper in `_update.py` with a direct `fmt_data(source_names)` call and delete the local helper.
- Audit other call sites that manually join formatted values and migrate them.
- Keep the single-value signature/behavior backward compatible so existing callers and tests are unaffected.

## Acceptance criteria

- `fmt_data([...])` / `fmt_ident([...])` return a sorted, comma-joined, individually-formatted string.
- `_update.py` no longer defines `_fmt_sources`; it calls the helper directly.
- `uv run tox` is green (all environments).

## Key files

- `src/repo_skills/console.py`
- `src/repo_skills/cli/_update.py`
- tests for the console helpers
