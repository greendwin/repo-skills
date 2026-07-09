# ADR-0001: CLI Output Styling Guide

**Status:** accepted
**Date:** 2026-05-21

## Context

CLI output used inconsistent colors and emoji across commands. Identifiers appeared
as `[green]`, `[cyan]`, or `[white]` depending on the file. Emoji appeared only in
merge output. Paths used `[cyan]` in some places and `[dim white]` in others.

## Decision

All CLI output uses Rich markup with these roles:

| Role | Markup | When |
|---|---|---|
| Identifier | `[green]` | Skill name, source name, provider name, branch |
| Command hint | `[blue]` | CLI flags and commands the user should run next |
| Path (in list output) | `[cyan]` | Paths that are the requested data (e.g. source list) |
| Path (in error/context) | `[dim]` | Secondary detail: repo paths, git output |
| Success message | plain text | Green only on identifiers inside, not the sentence |
| Warning | `[yellow]Warning:[/yellow]` | Prefix, rest is plain with styled identifiers |
| Error | `[red]Error:[/red]` | Prefix (handled by `error_handler`), identifiers still `[green]` |
| De-emphasized | `[dim]` | No-op results, secondary info |
| Section header | `[yellow]` | Group labels in list/status output |
| Emoji | none | Removed everywhere |

**Exceptions:** `skills status` uses color-as-status on names (`[green]synced`,
`[yellow]modified`, `[red]missing`, `[cyan]available`, `[dim magenta]orphan`).
This is a table-like layout where color _is_ the data — the guideline above
applies to prose messages, not tabular status.

### Error message structure

Errors have up to three parts: the error line, optional context, and optional hint.
Context stays directly under the error; hints get a blank line before them.

```
Error: <what went wrong>.
  <context key>: <context value>

<suggestion to fix>
```

Examples:

```
Error: Not on main branch (on 'dev', expected 'main').
  repo: /path/to/repo

Use --any-branch to override.
```

```
Error: No sources registered.

Run skills source init first.
```

```
Error: Repo has uncommitted changes.
  repo: /path/to/repo
```

> **Note (ADR-0007):** this role table is the styling *contract*; it is now
> *implemented* by cli-error's `DEFAULT_STYLES` theme (`id/data/path/cmd/warn/err`).
> The `status` color-as-data exception below stays raw markup, not a role.

## Consequences

- One color per semantic role — easier to apply consistently.
- No emoji — avoids terminal rendering inconsistencies.
- Success = calm (plain text) rather than celebratory (green sentence + emoji).
- Error identifiers stay `[green]` — the `[red]Error:[/red]` prefix carries the signal.
