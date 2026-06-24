---
id: s08t38
slug: unclear-error-on-install-failure
status: pending
---

# Unclear error on install failure

## Context

`skills install` gives unhelpful errors and isn't idempotent. Installing a batch (`s install a b c ...`) installs some, then errors midway on the first problem — leaving a partial install. The "Multiple sources registered (X, Y)" error never names the offending skill and conflates two different situations. Goal: pre-validate all names and report all problems *before* any provider write, skip already-installed skills idempotently, and make the multi-source error name the skill and list only the relevant sources.

## Decisions

- **Split the misleading "Multiple sources registered" error** — `_resolve_source` collapses two cases into one wrong message. Branch on `len(matches)`: `>1` → `"Skill <name> is available from multiple sources (<A>, <B>). Use --source to specify."` (names the skill, lists only sources that actually have it); `==0` → `"Skill <name> not found in any registered source."` (a not-found error — `--source` wouldn't help); no sources registered → unchanged. *Rejected: keeping the single message — it never names the skill and wrongly suggests `--source` for not-found.*
- **Two-pass install** — Pass 1 classifies every name with no provider writes: resolve source (collecting ambiguous / not-found / bad-`--source` errors), `prepare_source_repo` (checkout + pull, once per source), confirm the skill exists, classify as error / skip / installable. Pass 2: if Pass 1 produced *any* error → abort reporting **all** collected errors at once, having written nothing; otherwise copy + record each installable and print skip warnings. "Real installation" deferred to Pass 2 = the provider copy + manifest record only; pulling/checkout is part of Pass 1 (not "installing into a provider"). *Rejected: fail-on-first (leaves partial installs and surfaces one error at a time).*
- **Idempotent skip = manifest-tracked** — `skill_name in manifest.skills` → already installed: without `--force`, warn `"<name> already installed; use --force to reinstall."` and skip (no copy, no re-record), continue the batch; with `--force`, re-copy + re-record. An **untracked** dir collision (not in manifest but `install_path/<name>` exists — an orphan/mergeable dir) still **errors** without `--force`: `"<name> already exists at provider <p> but isn't tracked; use --force to adopt it."` — silently skipping or clobbering a hand-placed dir would be wrong. *Rejected: treating any existing provider dir as "already installed" — conflates tracked installs with manual/orphan dirs.*

## Edge cases

- A skill can collide at one provider but not another (multi-provider); per-provider dst existence drives the untracked-collision error.
- Batch where every name is already tracked: nothing to do, only skip warnings.
- `--force` on a tracked skill reinstalls; on an untracked collision adopts it into the manifest.

## Key files

- `src/repo_skills/cli/_install.py` — `_resolve_source` (split error), `install` (two-pass restructure), `_install_one` / `_copy_skill` (idempotent skip vs untracked-collision error).
- `src/repo_skills/config/_skill_manifest.py` — `manifest.skills` membership for the tracked check.

## Acceptance criteria

- `install <skill>` where the skill is in two sources: error names the skill and lists only those two sources.
- `install <skill>` where the skill is in no source: distinct not-found error, no `--source` suggestion.
- `install a b c` where `c` is invalid: nothing installed (a, b not written), all errors reported together.
- `install <tracked>` without `--force`: warning + skip, exit success; with `--force`: reinstalled.
- `install <name>` where an untracked dir exists at a provider: error requiring `--force`; with `--force`: adopted into manifest.

## Open questions

- None.

## Out of scope

- Changing `update`/`merge` ambiguity messages (this task is `install` only).
