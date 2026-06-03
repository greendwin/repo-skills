# Source setup exposed as `skills init` and `skills source config`

Setting up and editing a source is one idempotent create-or-update operation, exposed under two intent-named, behaviorally-identical commands: `skills init` (reads as "first-time setup") and `skills source config` (reads as "edit this source's settings"). Both accept `--name`, `--branch`, and `--skills-dir`, and both create the source if absent or edit it if present. `skills source init` is retained as a hidden alias so existing muscle memory keeps working.

This supersedes the s06t10 decision, which made top-level `skills init` a hidden redirect that errored with "Did you mean `skills source init`?" to teach the canonical command without silently forwarding. Once the command genuinely performs setup, that teaching rationale no longer applies, and a hidden-but-working command would be the worst case — exactly the silent forward s06t10 wanted to avoid, only undiscoverable. So `skills init` becomes a visible, first-class command.

## Considered Options

- **One overloaded `skills source init`** (status quo) that both creates and reinits. Works, but the name communicates only the create intent, so editing settings later reads as re-initializing.
- **Two intent-named commands over one shared implementation.** `init` for the create-oriented first run, `source config` for the edit-oriented later runs — like `git init` vs `git config`. Communicates intent at near-zero implementation cost since both route to the same idempotent logic.
- **Rename outright, dropping `skills source init`.** Cleaner surface, but breaks muscle memory and existing tests for no real gain pre-1.0; the hidden alias costs almost nothing.

## Consequences

- `CONTEXT.md`'s "Source" definition is updated to cite `skills init` (configurable later via `skills source config`) instead of `skills source init`.
- The two visible commands must never drift — they share a single implementation; the hidden `source init` alias targets the same one.
