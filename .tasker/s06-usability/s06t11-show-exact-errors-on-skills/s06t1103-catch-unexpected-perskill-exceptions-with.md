---
id: s06t1103
slug: catch-unexpected-perskill-exceptions-with
status: done
---

# Catch unexpected per-skill exceptions with --debug traceback

Wrap the per-skill body in `try/except Exception`. On catch:
- Print `Updating <skill> ... error: <str(ex)>`
- If `--debug` (`_print_callstack`): print traceback immediately via `console.print_exception()`, then continue

The skill is skipped but the batch continues. Manifest is not updated for failed skills.

Tests: simulate an unexpected exception (e.g. monkeypatch `compute_file_hashes` to raise); assert error line appears, other skills still update, and `--debug` produces traceback output.
