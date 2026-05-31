---
id: s09t07
slug: qa-triage-skill
status: pending
---

# QA triage skill

## Goal

`.claude/skills/qa-triage/SKILL.md` — a project-level skill that instructs the agent to scan integration test logs, identify issues beyond what assertions catch, and create Tasker tickets after user approval.

## Decisions & constraints

- Convention-based boundary: tests assert correctness (exit codes, expected output), skill reviews communication quality (style, clarity, consistency, UX flow).
- Checks four categories: behavioral inconsistencies outside assertion scope, output style/coloring issues, error message quality, UX flow issues.
- Report-then-batch-approve workflow: writes full report to `$ENV/qa-report.md`, presents numbered summary, user approves which become tickets.
- Tasker MCP for ticket creation.
- Supports full env scan or filtered by command name.
- Project-level, flat under `.claude/skills/`.

## Key files

- `.claude/skills/qa-triage/SKILL.md` (new)

## Acceptance criteria

- Skill prompt instructs scanning `$ENV/logs/` directory
- Categorizes findings into: behavioral, style, error quality, UX flow
- Outputs structured markdown report to `$ENV/qa-report.md`
- Presents numbered summary and creates Tasker tickets for user-approved findings
- Supports filtering to scope analysis to specific commands
- Skill file is valid and discoverable by Claude Code
