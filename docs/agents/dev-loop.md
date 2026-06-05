# Dev loop

This repo runs inside **Claude Code**. The code-review lenses invoke the built-in
`/code-review` command (read-only by default); the refactor lenses run the built-in
`/simplify` in a **throwaway scratch worktree** and capture the diff it produces as
their proposal — `/simplify` never touches the tracked tree, so `dev-loop`'s
single-writer invariant holds (only `tdd` applies the accepted hunks). Each lens below
is one reviewer; `dev-loop` spawns the lenses in a roster in parallel and collects
their findings. This document is self-contained — no other file is needed to perform
any lens below.

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
filesystem or `tmp_path`, and patch via the imported module object rather than a
string path or `unittest.mock.patch`. Report gaps and weak tests as findings. Do not
edit code; propose only.

### security

Review the change under review for security and data-safety issues: input handling and
validation, path traversal, injection, secret leakage in logs or errors, and any
operation that could lose or corrupt user data (e.g. overwriting or deleting tracked
files without a guard). Report each issue as a finding with its location, severity, and
a suggested fix. Do not edit code; propose only.

### performance

Review the change under review for performance: redundant filesystem walks or repeated
reads of the same source, accidental O(n^2) passes over sources/skills, work done
eagerly that could be lazy, and unnecessary allocations on hot paths. Flag only
defensible regressions or clear wins — do not invent micro-optimizations that hurt
clarity. Report each as a finding with its location and rationale. Do not edit code;
propose only.

## `refactor-reviewer`

Runs against the whole change during the refactor phase.

### simplify

Create a **throwaway scratch worktree** of the change under review, run the built-in
`/simplify` inside it, and **capture the diff it produces** — then discard the
worktree without touching the tracked tree. Report each simplification as a finding
whose `suggested-fix` is the captured hunk(s), with its location and rationale.
Propose only: you never write the tracked tree — `dev-loop` hands accepted hunks to
`tdd`, which applies them verbatim (repairing or dropping any that redden the suite).

### deep-modules

Review the change for shallow modules that should be deepened: thin wrappers that add
no abstraction, interfaces that leak implementation detail to their callers, and
primitive obsession where a small domain type (source, skill, provider) would hide
complexity behind a simpler interface. Push toward modules whose interface is small
relative to the functionality they provide. Report each opportunity as a finding
(location + rationale + suggested refactoring). Propose only; `dev-loop` hands accepted
proposals to `tdd` to apply.

### duplication

Review the change for duplication to extract: near-identical blocks across sources or
skills handling, repeated parsing/formatting logic, and parallel code paths that have
drifted and should be unified behind one helper. Distinguish true duplication from
incidental similarity — only flag cases where a single point of change is clearly
better. Report each as a finding (location + rationale + suggested extraction). Propose
only; `dev-loop` hands accepted proposals to `tdd` to apply.
