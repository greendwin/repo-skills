# Skills directory detection on `source init`

## Context

A source repo can hold its skills in more than one place (e.g. `claude/skills/…`
alongside `copilot/…`), and skills may sit at any depth. The original
single-`skills_dir` auto-detection silently fell back to an empty top-level
`skills/` directory whenever it could not find a single common parent — including
when real skills existed but were spread across the repo root. That produced a
source configured to scan an empty directory while its actual skills were
ignored.

## Decision

A source now stores a *list* of skills dirs (`source.json` schema version `1`,
field `skills_dirs`; legacy single-string `skills_dir` is migrated on load).

`source init` resolves the dirs as follows:

- **No `SKILL.md` anywhere** → fresh repo → create and use the default `skills/`.
- **All skills share one common dir below the repo root** → auto-detect that dir.
- **Skills straddle the repo root** (common ancestor *is* the root) → **error and
  require the user to pass an explicit `--skills-dir` list**. The tool never
  guesses here and never assumes an empty default while skills exist.

The **first** dir in the list is the *active* dir: the destination when a merged
orphan skill is written back into the source. A skill leaf name that appears in
more than one dir is a **collision** — it is excluded from the source's resolved
skills (reported, non-fatal), keeping the source usable for its other skills.

## Considered Options

- **Auto-detect the multi-dir list** (take the distinct parent dirs of every
  discovered skill). Rejected: categories make a skill's parent an unreliable
  signal for "skills dir," and inferring a list that scans large parts of the
  repo is exactly the silent-wrong-guess behaviour we set out to remove. Making
  the user state the dirs is explicit and safe.
- **Error on collision instead of dropping** the skill. Rejected: a single
  mirrored skill would otherwise make the whole source unusable for `install` /
  `update` / `status`.
