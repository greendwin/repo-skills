---
id: s08t39
slug: audit-path-manipulations-for-windows
status: pending
---

# Audit path manipulations for Windows compatibility

## Origin

Surfaced during s08t23 refactor review (dev-loop). The team confirmed this is **NOT a Linux-only project** — Windows must be supported. Several path-handling decisions in the codebase silently assume POSIX semantics and need a dedicated audit.

Governed by **`docs/adr/0006-cross-platform-path-handling.md`** — this task is the concrete audit that brings the code into line with that ADR.

## Goal

Audit and harden **all** path manipulations across `repo_skills` so behavior is correct on Windows as well as POSIX.

## Known concrete items to check (non-exhaustive)

- **`discovery.path_within`** — now uses `Path.is_relative_to`, which is **case-insensitive** on `WindowsPath` but the previously-used `.parts` tuple comparison was case-sensitive. Decide and document the intended containment case-semantics (NTFS is case-insensitive; is that desired for skills-dir containment?). Note its `is_absolute()` assert does NOT catch Windows drive-relative paths (`C:foo`).
- **`discovery.detect_skills_dir`** — compares `common.parts == git_root.parts` (deliberate `.parts` compare for path-flavour robustness). Confirm this is correct/consistent on Windows (drive letters, case).
- **`rel_posix` / POSIX-normalized repo-relative paths** — verify round-tripping and comparison of stored `skills_dirs` works when the repo lives on a Windows drive; ensure separators (`/` vs `\`) don't break lookups or the stored `source.json` values.
- **Drive-relative and UNC paths** — `.resolve()` behavior, `is_absolute()` semantics (`C:foo` is drive-relative and NOT absolute), and any `path_within`-style asserts that check `is_absolute()`.
- **Symlink / junction resolution** differences between platforms.
- **`Path.cwd()` / git-root discovery** and any string-path joins or manual separator handling.
- Gitignore / `.gitkeep` file writing paths.

## Acceptance

- A pass over the path-handling surface (discovery, cli/_source, cli/_merge, config, manifest) documenting or fixing each POSIX-only assumption.
- Ideally Windows coverage in CI (or platform-parametrized tests) so regressions are caught.

## Out of scope

- Reworking the skills-dir detection model (settled in s08t23).
