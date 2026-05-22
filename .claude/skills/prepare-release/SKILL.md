---
name: prepare-release
description: Prepare a release — bump version, draft release notes, check architecture doc drift, run tox. Never commits or tags.
disable-model-invocation: true
---

# prepare-release

A **tier-1** release skill: mutate files, run checks, print next steps. Never run `git commit`, `git tag`, or `git push`. The user reviews the diff and ships manually.

Optional argument: `major`, `minor`, `patch`, or an explicit `X.Y.Z` — sets the version directly. If absent, the skill reasons about the bump from commits and picks automatically.

---

## Flow overview

```
1. Pre-flight checks
2. Detect baseline tag
3. Read commits since baseline
4. Decide version
5. Discover architecture docs
6. Draft README release notes + check architecture doc drift
7. Write pyproject.toml, README.md, architecture docs
8. uv lock --upgrade (if uv.lock exists)
9. uv run tox (with one retry on skill-caused failures)
10. Print final output with suggested git commands
```

Every step has a stop condition. When a stop condition fires, leave whatever has been written on disk, print why, and exit. Do not attempt to roll back file changes — the user will review via `git diff`.

---

## 1. Pre-flight checks

Before mutating any files, verify the working state.

**Check A — tracked-file cleanliness.** Run `git status --porcelain`. If any line starts with `M`, `A`, `D`, `R`, or `C` (tracked file modifications), the tree is dirty. Untracked files (`??`) are ignored.

**Check B — on main branch.** Run `git rev-parse --abbrev-ref HEAD`. If not `main`, stop candidate.

On either failure, prompt the user interactively: show the specific problem (file list for dirty, branch name for wrong branch) and ask `Proceed anyway? [y/N]`. Default is no. Only proceed on explicit `y`.

No `--force` flag. The interactive prompt is the only override path.

## 2. Detect the baseline tag

The baseline tag defines "previous release" — the point from which commits are diffed.

Algorithm:
1. Read the current version from `pyproject.toml` (`[project] version = "X.Y.Z"`).
2. Look for a tag `vX.Y.Z` matching that version. If found, that's the baseline.
3. Otherwise, list all tags matching `vX.Y.Z` (stable only — exclude anything with `a`, `b`, `rc` suffixes) and find the highest one ≤ the pyproject version. That's the baseline.
4. If multiple tags could plausibly match, or nothing is resolvable, **ask the user** which tag to use as baseline. Do not guess.

**Stop conditions:**
- No prior stable release tag exists at all → stop. "No prior release tag found; prepare-release assumes an existing release baseline. First releases must be cut manually."
- Ambiguity the user cannot resolve → stop.

## 3. Read commits since baseline

Run `git log --no-merges --format="%H %s" <baseline>..HEAD` to get the commit list.

**Stop condition:** if the list is empty, stop. "Nothing to release since `<baseline>`."

Store the commit list — you'll need the subjects for version reasoning and the full messages (+ optional diffs) for ambiguous cases and architecture doc drift detection.

## 4. Decide version

Determine the version bump before drafting notes.

**Version reasoning approach:**
- Read all commit subjects.
- For commits with vague prefixes (`ref:`, `chore:`, `update`, no prefix), read the commit body or run `git show --stat <hash>` to understand what actually changed.
- Apply standard semver: breaking changes → major; new user-visible features → minor; bug fixes + internal refactors → patch.
- Watch for hidden breaking changes: dependency bumps that drop support for a Python version, CLI flag removals, file format changes, public API signature changes. A commit titled `ref:` can still break users.
- If the user passed an argument (`major` / `minor` / `patch` / `X.Y.Z`), use that version. Still note what the skill would have chosen for transparency in the final report.

**Prefix tally as sanity check:** count prefixes (`feat:`, `fix:`, etc.). If the tally disagrees with the proposed bump (e.g., 5 `feat:` commits but proposing patch), note the disagreement in the version reasoning.

**Validation (for explicit version arguments):**
- Lower than current → stop. "Cannot bump to X.Y.Z — not greater than current A.B.C."
- Already has a tag (`git rev-parse vX.Y.Z` succeeds) → stop. "Version X.Y.Z already released."
- Prerelease format (`1.4.0a1`, `2.0.0rc2`) → allow but skip README release notes (only bump pyproject).
- Any valid greater stable semver → accept.

## 5. Discover architecture docs

Identify architecture docs to check for drift. Use the **union** of two discovery channels:

**Channel A — CLAUDE.md references.** Parse `CLAUDE.md` (if it exists) for references to `.md` files that look like architecture or design docs. Examples: `CONTEXT.md`, `DESIGN.md`, `STRUCTURE.md`, `docs/adr/`, etc.

**Channel B — auto-detect known filenames.** Scan the repo root for: `DESIGN.md`, `CONTEXT.md`, `STRUCTURE.md`, `ARCHITECTURE.md`. Also glob `docs/adr/*.md` if that directory exists.

Deduplicate the union. Exclude files that don't exist. ADR files (`docs/adr/*.md`) are point-in-time decision records — **do not** drift-check them. Only include them in the discovered set for awareness in the final output.

Store the discovered list for steps 6 and 10.

## 6. Draft README release notes + check architecture doc drift

Nothing is written to disk yet.

### README release notes

Goal: produce a new `### vX.Y.Z` section for `README.md`'s `## Release Notes` that matches the house style.

**Learn the style:** read the two most recent release sections to calibrate voice, bullet phrasing, grouping conventions, and prefixes.

**Drafting rules:**
- Curate, don't enumerate. Collapse related commits into one bullet. Drop commits that are pure internal churn (version bumps, tox config tweaks, CI noise) unless they affect users.
- Keep bullets short — one line each is the norm.
- Match tense and phrasing style of existing release sections.

### Architecture doc drift check

Goal: keep architecture docs honest about the current state, but only touch sections this release actually affects.

**Step 1 — is drift checking relevant at all?** Scan the release's commits. Architecture docs are implicated if commits touch:
- CLI command surface (new commands, new flags, changed behavior of existing commands)
- Public API surface (new types, changed signatures, removed exports)
- Configuration file format (new fields, changed structure)
- Key terminology or concepts (new terms, renamed terms, removed terms)

If no commits match, **skip this step entirely** and report: "Architecture docs: no drift detected for this release."

**Step 2 — surgical edits.** For each implicated architecture doc:
1. Grep the actual source for the current surface (e.g., Typer commands, public API types, config models).
2. Read the matching section of the architecture doc.
3. Identify the specific lines that are stale and propose minimal edits — new row in a table, one new bullet, one updated sentence.

Do **not** rewrite whole sections. Do **not** "improve" prose that is merely dated in style rather than factually wrong. Do **not** audit unrelated sections just because they happen to be nearby.

**Scope discipline:** only check drift caused by *this release's* commits. A full architecture doc vs source audit is a separate concern and out of scope for this skill.

## 7. Write the files

After drafting, write immediately — no approval gate:
1. Update `pyproject.toml`: change the `version = "X.Y.Z"` line under `[project]`. Do not touch anything else in that file.
2. Prepend the new `### vX.Y.Z` section to `README.md`'s `## Release Notes` (directly above the previous release entry). Skip this for prerelease versions.
3. Apply the architecture doc edits if any.

## 8. Idempotent re-run detection

The skill may be re-invoked mid-flow — e.g., tox failed, user fixed something, runs `/prepare-release` again. Detect this at **step 1** and adapt:

**In-progress release signal:** `pyproject.toml` version is greater than the highest stable tag *and* `README.md` already has a `### v<that version>` section.

When detected:
- Skip version decision and file writes (already done).
- Resume at `uv lock --upgrade` → `tox` → final output.
- Announce clearly: "Detected in-progress release vX.Y.Z — resuming from lockfile step."

The user can force a fresh run by manually reverting `pyproject.toml` before re-invoking.

## 9. Refresh dependencies

Run `uv lock --upgrade` only if `uv.lock` exists in the repo root. This refreshes `uv.lock` against the newest versions allowed by the existing constraints in `pyproject.toml`.

If `uv.lock` does not exist, skip this step entirely.

**Do not** edit constraint floors (`typer>=0.9.0`) or ceilings in `pyproject.toml`. Raising floors is a support-policy decision; ceilings exist because upstream has known breakage. If `uv lock --upgrade` surfaces newer versions that are blocked by ceilings, mention it in the final output as an FYI — do not act on it.

**Stop condition:** if `uv lock --upgrade` fails (resolution conflict, network error, etc.), stop immediately. Print the error. "Release blocked by dep resolution. Fix constraints manually and re-run."

## 10. Run tox

Run `uv run tox`. This is the acceptance gate.

**On success:** proceed to final output.

**On failure:** look at the failure output. Two cases:

**Case A — plausibly caused by this skill's edits.** Formatting (`black`), import sort (`isort`), trailing whitespace, line-too-long in README.md, simple type errors on files the skill touched. Apply the fix (run `uv run black`, `uv run isort`, or edit the offending line) and re-run `uv run tox` **once**. If still red, stop.

**Case B — not caused by this skill.** Test failures in unrelated code, type errors in source files the skill didn't touch, tool version incompatibilities, missing test fixtures. Stop immediately. "Tox failure unrelated to release prep — fix and re-run. Pre-existing failures are out of scope for this skill."

Never skip hooks, never `--no-verify`, never edit `tox.ini` to quiet errors.

## 11. Final output

On success, print a single summary block. This is where all the information that was previously shown at the gate is presented — the user reviews everything after the work is done.

```
Release prep complete: vX.Y.Z

Commits since v<baseline> (<N>):
  - <commit subject 1>
  - <commit subject 2>

Version: X.Y.Z (patch|minor|major)
Reasoning: <brief explanation of why this bump level was chosen,
including any uncertainty or prefix-tally disagreements>

=== README.md (written) ===

### vX.Y.Z
- <release note 1>
- <release note 2>

=== Architecture docs ===

<edits applied per file, or "No drift detected for this release.">

Discovered architecture docs:
  CONTEXT.md             checked
  docs/adr/0001-...md    skipped (ADR)

Changed files:
  pyproject.toml       <N> +, <M> -
  uv.lock              <N> +, <M> -   (or: skipped — no lockfile)
  README.md            <N> +
  CONTEXT.md           <N> +, <M> -   (or: unchanged)

Tox: passed

Suggested next steps (run yourself):
  git add <list of changed files>
  git commit -m "<commit message in house style>"
  git tag vX.Y.Z
  git push && git push --tags
```

If the user passed an explicit version that differs from what the skill would have chosen, include a note: "User-specified version X.Y.Z (commits suggest <bump level>)."

**Commit message style:** read the most recent release commit (search `git log` for the commit that last bumped the version in `pyproject.toml`) and match its phrasing. If no prior release commit exists, calibrate the prefix from recent commits and fall back to `release vX.Y.Z`.

Do **not** execute any `git` command. Print and stop.

---

## Stop conditions — quick reference

| When | Action |
|---|---|
| Dirty tracked tree, user declines override | Stop, report dirty files |
| Not on `main`, user declines override | Stop, report branch |
| No baseline tag found | Stop, "first releases must be cut manually" |
| Baseline ambiguous and user cannot resolve | Stop, ask what they want |
| Zero commits since baseline | Stop, "nothing to release" |
| Explicit version ≤ current or already tagged | Stop, report invalid version |
| `uv lock --upgrade` fails | Stop, report error |
| Tox fails and cause is not skill-caused | Stop, "fix pre-existing and re-run" |
| Tox still fails after one auto-fix retry | Stop, report remaining issues |

## What this skill never does

- Never runs `git commit`, `git tag`, `git push`, or any other mutating git command.
- Never edits `pyproject.toml` constraints (only the `version` field).
- Never touches `tox.ini` or CI configuration.
- Never uses `--no-verify`, `--no-gpg-sign`, or equivalent skip-hook flags.
- Never rewrites architecture doc sections that aren't implicated by this release.
- Never edits files outside: `pyproject.toml`, `uv.lock`, `README.md`, and discovered architecture docs.
