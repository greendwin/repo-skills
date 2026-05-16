---
id: s01
slug: build-skill-cli-for-managing
status: pending
---

# Build `skill` CLI for managing Claude Code skills

## Decisions

- **Python 3.10+ / uv / click / prompt_toolkit** — broad compatibility; click for CLI structure; prompt_toolkit for interactive skill selection
- **Dev tooling: black, isort, mypy (strict), flake8** — enforces code quality and type safety from the start
- **Package `skill_cli` in `src/` at repo root, `skill` entry point** — avoids name collision with `skills/` content directory; `pyproject.toml` at repo root
- **Six commands: install, update, peek, merge, list, uninstall** — complete lifecycle management for skills
- **File copy with central manifest (`~/.claude/skills/.skill-install.json`)** — decoupled from repo location; manifest tracks source repo path + git commit hash per skill
- **Repo discovery: git root if inside repo, else manifest's stored path** — `skill install` works inside repo; `peek`/`update` work from anywhere
- **Peek shows both directions, summary by default, `--diff` for details** — answers "what's out of sync?" quickly; drill into file diffs when needed
- **Update aborts on conflict, `skill merge <name>` for resolution** — merge creates `skill-merge/<name>` branch from stored commit, commits local edits, rebases onto current branch, fast-forwards main on success (fail if can't FF, never push)
- **Merge is stateless — branch existence is the state** — `--continue`/`--abort` with optional `<name>` (required if multiple merges active); dirty working tree aborts early
- **Thin git wrapper (`GitRepo`) + pyfakefs** — core logic tested with fake filesystem; git wrapper gets integration tests with real temp repos via `tmp_path`
- **Interactive `skill install` (no args) via prompt_toolkit** — shows uninstalled skills for selection
- **`skill list` shows repo skills + orphans** — full picture of available, installed, and orphaned skills
- **Public API via `__init__.py`, all submodules `_`-prefixed** — per project convention
- **No real filesystem in tests** except git integration tests for the thin wrapper — per project convention

## Subtasks

- [x] [s01t01](s01t01-slice-1-project-scaffold.md): Slice 1 — Project scaffold
- [x] [s01t02](s01t02-slice-2-repo-discovery-skill.md): Slice 2 — Repo discovery + `skill list`
- [x] [s01t03](s01t03-slice-3-skill-install-name.md): Slice 3 — `skill install <name>` + `skill uninstall <name>`
- [ ] [s01t04](s01t04-slice-4-skill-update-name.md): Slice 4 — `skill update [name]`
- [ ] [s01t05](s01t05-slice-5-skill-peek-diff.md): Slice 5 — `skill peek [--diff] [name]`
- [ ] [s01t06](s01t06-slice-6-interactive-skill-install.md): Slice 6 — Interactive `skill install` (no args)
- [ ] [s01t07](s01t07-slice-7-skill-merge-name.md): Slice 7 — `skill merge <name>` + `--continue` / `--abort`
- [x] [s01t08](s01t08-rework-cli-from-click-to.md): Rework CLI from click to typer + typer_di
- [x] [s01t09](s01t09-list-command-should-be-pretty.md): List command should be pretty
