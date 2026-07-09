---
id: s04t1003
slug: repo-skills-fmt-absorption-retire
status: pending
---

# Repo_skills fmt-absorption: retire fmt_* for cli-error roles

## Goal

The parallel styling vocabulary is gone: `fmt_ident/data/path/command` deleted, ~30 call sites rewritten to `reporter.print` templates with auto-escaped args using cli-error's semantic roles, and the `status` color-as-data markup left raw. Output is visually identical; the `fmt_*` names no longer exist anywhere in `src/`. Depends on slice 2 (s04t1002).

## Decisions & constraints

- **Delete `fmt_ident/data/path/command`; call sites move to `reporter.print` templates with escaped args** — `console.print(f"…{fmt_ident(x)}…")` → `reporter.print("…[id]{x}…", x=x)`. Roles map: `fmt_ident`→`[id]`, `fmt_data`→`[data]`, `fmt_path`→`[path]`, `fmt_command`→`[cmd]`. This upgrades today's manual `escape()`-inside-each-helper to cli-error's auto-escaping. *Rejected: thin `fmt_*` wrappers emitting role markup — retains the vocabulary this task retires.*
- **Status color-as-data stays raw** — `STATUS_MISSING`/`SYNCED`/`MODIFIED`/`ORPHAN` (`[green]synced`, `[yellow]modified`, `[red]missing`, `[cyan]available`, `[dim magenta]orphan`) are *not* semantic roles; color *is* the datum there (ADR-0001 explicit exception). Do not convert to `[id]`/etc. cli-error's theme (`id`≡green) sits alongside raw rich colors without conflict, so output is unchanged.

## Edge cases

- Roles must resolve identically to the old raw colors: `id`≡green, `data`≡cyan, `path`≡dim, `cmd`≡blue — verify no visual diff.
- `prop_*` on the typed subclasses (from slice 2) already use roles; this slice only touches the free `fmt_*` call sites in prose/print output.
- Mixed lines (identifier + path in one message) become a single template with multiple escaped args, not nested `f"{fmt_...}"` calls.
- `fmt_data` handles `list[str]` (sorted, comma-joined) — preserve that behavior when converting its call sites (either a small template loop or a joined arg).

## Key files

- `src/repo_skills/console.py` (delete `fmt_ident/data/path/command`).
- Call sites (~30): `git_real.py`, `git.py`, `cli/_provider.py`, `cli/_update_attach.py`, `cli/_source.py`, `cli/_install.py`, `cli/_update.py`, `cli/_status.py`, `cli/_merge.py`, `config/_provider_registry.py`, `config/_source_registry.py`, `config/_source.py`.
- `src/repo_skills/cli/_status.py` (leave `STATUS_*` raw).
- Tests asserting on styled output.

## Acceptance criteria

- `grep -rn "fmt_ident\|fmt_data\|fmt_path\|fmt_command" src/` is empty.
- CLI output (identifiers, paths, commands, data) is visually identical to before, verified on `status`/`source`/`merge` output.
- The `status` table still renders `[green]synced`/`[dim magenta]orphan`/etc. as raw color-as-data.
- `uv run tox` green (all environments).
