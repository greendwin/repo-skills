---
id: s06t10
slug: improve-source-init-reinit-feedback
status: pending
---

# Improve `source init` re-init feedback & add hidden `skills init`

## Decisions

- **Grouped output format** — changes reported as indented detail lines under a header (`key: old → new`), so feedback is organized together rather than scattered independent messages
- **"Updated" header for changes** — `Updated source X.` when something changed; `Source X already initialized.` only for true no-op
- **Rename folded into same pattern** — `name: foo → bar` as a detail line, consistent with branch changes instead of a special-cased header
- **Re-registered keeps distinct header** — `Registered source X.` stays (restoring missing registry entry is a different situation), with detail lines underneath if applicable
- **Hidden `skills init` redirect** — top-level `skills init` (hidden from help) prints "Did you mean 'skills source init'?" and exits non-zero, teaching the correct command without silently forwarding

## Key files

- `/work/src/repo_skills/cli/_source.py` — `_handle_reinit()` (lines 49-89), main target
- `/work/src/repo_skills/cli/_app.py` — register hidden `init` command

## Subtasks

- [x] [s06t1001](s06t1001-grouped-feedback-in-handlereinit.md): Grouped feedback in `_handle_reinit`
- [ ] [s06t1002](s06t1002-hidden-skills-init-redirect-command.md): Hidden `skills init` redirect command
