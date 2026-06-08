---
id: s10t02
slug: rework-repo-workflow
status: done
---

# Rework repo workflow

Rework the repo-skills CLI to support multiple source repos, multiple agent providers, and bidirectional skill editing.

## Decisions

- **Any git repo can be a source** — `source init` registers an arbitrary repo as a skills source, not just dedicated skills repos.
- **"Source" is the canonical term** — a registered repo is a "source," the collection is the "source registry."
- **`.repo-skills/` directory in source repo** — created by `source init`, gitignored with `*`, contains `source.json` (name, skills_dir). Everything untracked.
- **Global config at `~/.config/repo-skills/`** (XDG) — `sources.json`, `manifest.json`, `providers.json` all live here.
- **Source name auto-derived from directory** — defaults to repo directory name, `--name` override. Must be unique.
- **Categories are organizational only** — subdirectories under skills root for grouping. Skill identity is leaf directory name, must be globally unique.
- **Max depth 3 for auto-detection only** — during `source init` on populated repos. After init, any depth under registered root; skills found by `SKILL.md` presence.
- **`source init` has two paths** — fresh repo (approve dir name, create with `.gitkeep`, support root-level) and populated repo (search for `SKILL.md`, guess root via deepest common ancestor, user approves/overrides).
- **Multi-provider: install targets all providers** — no `--provider` flag. Claude is built-in default. `provider add/list/remove` for others.
- **Installed copies are editable** — bidirectional flow: source ↔ providers. Edits merged back via `skills merge`.
- **Divergence detection via per-file content hashes** — stored in manifest at install time. Fast, no git checkout needed.
- **Single global manifest** — one `manifest.json` tracks baseline for all skills. Per-provider divergence checked at runtime.
- **Merge uses git branching** (s01t07 design) — branch from stored commit, rebase, FF-only. `--from` provider and `--to` source auto-detected when unambiguous.
- **`update` does `git pull` by default** — syncs source→providers, auto-installs to new providers, skips modified copies (no `--force`).
- **`install --force` only** — destructive overwrite is one skill at a time. No `--force` on `update`.
- **Command inventory:** `install`, `update`, `uninstall`, `merge`, `status` at top level. `source init/list/remove` and `provider add/list/remove` as subgroups.
- **Incremental refactor** — evolve existing codebase, keep patterns (GitRepo protocol, typer-di, pyfakefs, `assert_invoke`).

## Subtasks

- [x] [s10t0201](s10t0201-remove-unused-commands.md): Remove unused commands
- [x] [s10t0202](s10t0202-new-config-and-manifest-models.md): New config and manifest models
- [x] [s10t0203](s10t0203-skills-source-init.md): `skills source init`
- [x] [s10t0204](s10t0204-skills-source-list-skills-source.md): `skills source list` + `skills source remove`
- [x] [s10t0205](s10t0205-skills-provider-addlistremove.md): `skills provider add/list/remove`
- [x] [s10t0206](s10t0206-skills-install-reworked.md): `skills install` (reworked)
- [x] [s10t0207](s10t0207-skills-status.md): `skills status`
- [x] [s10t0208](s10t0208-skills-update-reworked.md): `skills update` (reworked)
- [x] [s10t0209](s10t0209-skills-uninstall-reworked.md): `skills uninstall` (reworked)
- [x] [s10t0210](s10t0210-skills-merge-continue-abort/): `skills merge` + `--continue` / `--abort`
- [x] [s10t0211](s10t0211-rename-installed-skills-on-source.md): Rename installed skills on source rename
- [x] [s10t0212](s10t0212-pinned-branch-in-source-init/): Pinned branch in `source init` + remove `--any-branch`
- [x] ~~s10t0213: Release v1.0~~
