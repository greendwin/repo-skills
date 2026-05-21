---
id: s01t09
slug: list-command-should-be-pretty
status: done
---

# List command should be pretty

Colorize and clarify `skill list` command output.

## Decisions

- **Add `rich` dependency** — provides full terminal formatting beyond what `typer.style()` offers
- **Grouped sections, not flat list** — makes it immediately obvious which skills are where without scanning every line
- **Section order: Installed → Not in repo → Not installed** — happy-path first; "Not in repo" (yellow) flags attention; "Not installed" (dim) is low-priority available actions
- **Section header colors: green / yellow / dim** — follows conventional terminal semantics (good / warning / inactive)
- **Skill entries: bright white name + em-dash + dimmed description** — name stands out, description provides context without competing visually
- **Description from SKILL.md frontmatter** — read from install dir for installed/not-in-repo, repo dir for not-installed; graceful fallback (name only) if missing
- **Hide empty sections** — no noise for categories with zero entries
- **Tests use NO_COLOR=1** — Rich respects this env var; tests assert plain text without ANSI stripping. Rewrite existing tests for new grouped format.
