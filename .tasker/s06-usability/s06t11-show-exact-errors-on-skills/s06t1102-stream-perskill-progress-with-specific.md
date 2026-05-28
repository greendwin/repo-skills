---
id: s06t1102
slug: stream-perskill-progress-with-specific
status: pending
---

# Stream per-skill progress with specific known-error messages

Replace `_print_report()` batch summary with per-skill `Updating <skill> ... <status>` lines printed as each skill is processed.

Replace bare `_ERROR` label with specific messages:
- Source not in registry → `error: source '<name>' not found`
- Skill not in source → `error: skill removed from source`

Remove `_print_report()` and the `results` list.

Tests: assert progress lines appear in correct order with correct statuses; assert known error messages are specific.
