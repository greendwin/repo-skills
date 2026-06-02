---
id: s06t16
slug: autoattach-untracked-skills-on-update
status: pending
---

# Auto-attach untracked skills on `update` when they match source exactly

## Context

Untracked dirs in provider install paths that exactly match a source skill currently require a manual `install --force`. `update` should attach them automatically — a non-destructive, manifest-only bookkeeping operation. There is an existing TODO in `_update.py` ("can we do anything with skills that are not in manifest?").

Depends on s06t18's collection model. Implementation order: **t18 → t16 → t19**.

## Decisions

- **Flows through t18's collection seam** — attach-candidates obey the same name/source filters and contribute to the derived pull set; the empty/no-op check runs *after* they're considered, so `-s X` with only untracked-but-matching skills still does useful work instead of no-opping. *Rejected: a separate attach pass outside the filter model.*
- **Matching & baseline** — match the installed copy's file hashes against the source skill's content at pinned-branch HEAD (the same content `update` would copy). On attach, record the baseline as that skill's commit + source hashes, mirroring how `install` records a baseline (`_record_manifest` / `_resolve_commit`). Set `detached=False`.
- **Ambiguity** — attach only when *exactly one* source matches by exact hash. Zero exact matches → leave as orphan/mergeable (untouched, as today). Multiple exact matches → skip with a note, don't guess. Under `-s X`, only source X is a candidate.
- **Output** — print a line like `Attached skill X (matched source Y)`. Modified copies stay untouched.
- Remove the `_update.py` TODO once implemented.

## Open questions

- Finer per-provider divergence (same skill clean in one provider, modified in another) — defer detail to this task's own TDD; the manifest is keyed by skill name, so existing per-provider update logic (exact match → up-to-date, modified → skipped) applies after attach.

## Out of scope

- Changing modified installed copies — attach is manifest-only; files are never written.
- The filter/collection model itself (owned by s06t18).

## Subtasks

- [ ] [s06t1601](s06t1601-attach-a-uniquelymatching-untracked-skill.md): Attach a uniquely-matching untracked skill
- [ ] [s06t1602](s06t1602-attach-ambiguity-handling-filter-integration.md): Attach ambiguity handling & filter integration
