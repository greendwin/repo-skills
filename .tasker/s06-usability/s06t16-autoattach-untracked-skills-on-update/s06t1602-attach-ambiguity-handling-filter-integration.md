---
id: s06t1602
slug: attach-ambiguity-handling-filter-integration
status: in-review
---

# Attach ambiguity handling & filter integration

## Goal

Attach respects source ambiguity and flows through s06t18's collection seam: attach-candidates obey `-s`/name filters, their sources join the derived pull set, and the empty/no-op check only fires when there are neither tracked skills nor attach-candidates.

## Decisions & constraints

- **Ambiguity** — attach only when *exactly one* source matches by exact hash. Zero exact matches → leave as orphan/mergeable (untouched). Multiple exact matches → skip with a note, don't guess.
- **Filter integration** — under `-s X`, only source `X` is an attach candidate; attach-candidates contribute to the derived pull set (so their source is pulled before matching).
- **Empty-check** — runs after attach-candidates are folded in, so `-s X` with only an untracked-but-matching skill does useful work instead of no-opping.

## Edge cases

- Same untracked name exists in two sources, both matching exactly → ambiguous, skip with note.
- `-s X` where the only relevant skill is an untracked match from `X` → attaches + updates, does not no-op.

## Key files

- `src/repo_skills/cli/_update.py`
- `tests/cli/test_update.py`

## Acceptance criteria

- Ambiguous (multi-source exact match) → skipped with a note, no attach.
- `-s X` with only an untracked match from `X` attaches and updates rather than emitting the empty no-op.
- Attach-candidate sources appear in the pull set.
