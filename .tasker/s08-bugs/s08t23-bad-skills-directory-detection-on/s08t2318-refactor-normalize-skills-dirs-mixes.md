---
id: s08t2318
slug: refactor-normalize-skills-dirs-mixes
status: in-review
---

# Refactor: `_normalize_skills_dirs` mixes path validation/normalization with user-facing console output

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "`_normalize_skills_dirs` mixes path validation/normalization with user-facing console output"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/cli/_source.py:129-145 (`_normalize_skills_dirs`)
- severity: minor

A function named `_normalize_skills_dirs` (which returns the normalized list) also performs the side effect of `console.print(...)` the 'currently has no skills' note per dir. Mixing a pure-looking transform with presentation output is a layering smell: the note fires for both fresh-init and reinit purely because validation runs before the fresh/reinit branch (the tests even comment on this incidental ordering). This makes the note's firing condition a side effect of where validation happens rather than an intentional decision, and couples normalization to the Rich console. Fixing it changes the helper's return contract (to also surface which dirs lack skills) and moves the note-emission decision into `_init_or_config_source`, altering caller control flow and the note's firing semantics — a genuine structural reshape best filed as a side-task seed rather than landed behavior-preservingly here.

## Suggested fix

Have `_normalize_skills_dirs` return the normalized dirs plus which ones lack skills (e.g. `tuple[list[str], list[str]]` or yield warnings), and let `_init_or_config_source` decide when/whether to emit the note, keeping the normalize helper free of console output.
