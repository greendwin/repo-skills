---
id: s06t11
slug: show-exact-errors-on-skills
status: pending
---

# Show exact errors on skills update

Replace batch summary in `skills update` with a streaming progress log.

## Output format

Flat list, no headers. One line per operation as it happens:

```
Pulling skills-repo ... done
Pulling other-repo ... skipped
Updating test ... updated
Updating test2 ... error: skill removed from source
Updating test3 ... up to date
```

## Statuses (color-coded)

- `[green]updated[/green]`
- `[dim]up to date[/dim]`
- `[yellow]skipped (modified)[/yellow]`
- `[yellow]detached (commit unreachable)[/yellow]`
- `[green]recovered[/green]`
- `[red]error: <message>[/red]`
- Pull done: `[green]done[/green]`
- Pull skipped (offline): `[dim]skipped[/dim]`

## Error handling

- Known errors get specific messages: `source 'foo' not found`, `skill removed from source`
- Unexpected per-skill exceptions caught inline; shown as `error: <str(ex)>`
- If `--debug`: traceback printed immediately when caught, then continue to next skill
- Pre-loop errors (source pull, branch validation) still abort via `error_handler`

## Not in scope

- Streaming git/subprocess invocations under `--debug` (separate task)

## Subtasks

- [x] [s06t1101](s06t1101-add-pull-progress-lines.md): Add pull progress lines
- [x] [s06t1102](s06t1102-stream-perskill-progress-with-specific.md): Stream per-skill progress with specific known-error messages
- [x] [s06t1103](s06t1103-catch-unexpected-perskill-exceptions-with.md): Catch unexpected per-skill exceptions with --debug traceback
- [x] [s06t1104](s06t1104-suppress-pyright-warnings-for-unused.md): Suppress Pyright warnings for unused _fake_git fixture params
- [ ] [s06t1105](s06t1105-show-perprovider-status-when-update.md): Show per-provider status when update results differ across providers
