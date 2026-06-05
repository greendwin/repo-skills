# Dev loop

This repo runs inside **Claude Code**. The code-review lens invokes the built-in
`/code-review` command (read-only by default); the refactor lenses are read-only
reviewers that propose refactorings in prose. Every lens reports findings with an
inline `suggested-fix` and never edits the tracked tree — `dev-loop` hands the accepted
findings to `tdd`, the sole writer, which implements them under green tests. Each lens
below is one reviewer; `dev-loop` spawns the lenses in a roster in parallel and
collects their findings. This document is self-contained — no other file is needed to
perform any lens below.

## `code-reviewer`

Runs against the implemented change once it is green.

### general

Invoke the `/code-review` built-in command over the change under review. Report every
issue it surfaces — correctness, missing/weak tests, security, and maintainability —
as findings. Do not edit code; propose only.

### tests

Review the change specifically for test quality: every new public behavior has a
behavior-level test, tests exercise the public interface (the package's `__init__.py`
re-exports, not `_`-prefixed submodule internals), and there are no
implementation-coupled or mock-heavy tests. Confirm tests use the `assert_invoke`
helper rather than `CliRunner` for CLI behavior, use `pyfakefs` rather than a real
filesystem or `tmp_path`, and patch via `monkeypatch` on the imported module object
rather than a string path or `unittest.mock.patch`. Report gaps and weak tests as
findings. Do not edit code; propose only.

### performance

Review the change under review for performance: redundant filesystem walks or repeated
reads of the same source, accidental O(n^2) passes over sources/skills, work done
eagerly that could be lazy, and unnecessary allocations on hot paths. Flag only
defensible regressions or clear wins — do not invent micro-optimizations that hurt
clarity. Report each as a finding with its location and rationale. Do not edit code;
propose only.

## `refactor-reviewer`

Runs against the whole change during the refactor phase.

### duplication

Review the change for repeated logic or structure — copy-pasted blocks, parallel
branches that differ only in a value, the same computation done in several places.
For each, name the duplicated sites and propose how to unify them (extract a helper,
parameterize, hoist a shared value). Distinguish true duplication from incidental
similarity — only flag cases where a single point of change is clearly better. Report
each as a finding with location, rationale, and an inline `suggested-fix`. Do not edit
code; propose only.

### deep-modules

Review the change for shallow modules — a large interface over thin implementation,
pass-through wrappers, and abstractions that leak their internals. Push toward modules
whose interface is small relative to the functionality they provide: collapse a
needless wrapper, hide complexity behind a smaller interface, or fold a one-call helper
into its caller. Report each as a finding with location, rationale, and an inline
`suggested-fix`. Do not edit code; propose only.

### simplification

Review the change for control-flow complexity — deep nesting, arrow code, redundant
conditionals, and branches that a guard clause or early return would flatten. Propose
the flattened form. Report each as a finding with location, rationale, and an inline
`suggested-fix`. Do not edit code; propose only.
