---
id: s08t2306
slug: status-shows-zeroskill-sources
status: in-review
---

# Status shows zero-skill sources

## Goal

A freshly-initialized source with no skills is visible in `skills status`: its `Source <name>` header is printed followed by a dim `(no skills)` placeholder line. Fixes Issue #1.

## Decisions & constraints

- **Source list from the registry** — In `_print_source_sections`, build `all_sources` from `source_registry.sources` (every *registered* source) unioned with `installed_by_source.keys()` (so sources lingering in the manifest after being unregistered still surface). Today `all_sources` is `installed_by_source ∪ available_by_source`, which omits a source that has neither — exactly the freshly-init'd case.
- **Zero-skill placeholder** — For a source that ends up with no installed and no available rows, print its `Source <name>` header (existing styling, including the `(broken)` marker path) followed by a single dim `  (no skills)` line. Match the existing `STATUS_*`/dim conventions; the placeholder is a separate dim line under the header (not appended to the header).
- The function must still return `has_output = True` for such a source so the command does not fall through to the `No skills found.` `NoopError`.

## Edge cases

- A broken source with no skills → still shows the `Source <name>  (broken)` header (existing path); `(no skills)` line not needed there (broken short-circuits skill listing).
- A source registered AND with available/installed skills → unchanged output.
- A source present only in the manifest (unregistered) with installed skills → still listed (union with `installed_by_source.keys()`).
- Blank-line separation between source sections must remain correct (the existing `if has_output: print("")` spacing).

## Key files

- `src/repo_skills/cli/_status.py` — `_print_source_sections` (the `all_sources` construction and per-source loop), `status`.
- Tests: `tests/cli/test_status.py`, `tests/cli/helper.py` (source/registry setup helpers).

## Acceptance criteria

- After `source init` on a repo with no skills, `skills status` prints `Source <name>` and a dim `(no skills)` line (instead of `No skills found.`).
- A registered source with skills is unchanged.
- An unregistered-but-installed source still appears.
- Section spacing (blank lines between sources and before the Untracked block) is preserved.
- `uv run tox` green.
