---
id: s01t03
slug: integration-tests-and-qa-skills
status: pending
---

# Integration tests and QA skills

## Context

The `repo-skills` CLI has unit tests that mock git and the filesystem via `pyfakefs`/`FakeGitRepo`, and a small set of `RealGitRepo` unit tests. There are no end-to-end integration tests that exercise CLI commands against real git repos on a real filesystem. We also lack agent-driven QA tooling to catch subtle output issues (style inconsistencies, misleading messages, UX flow problems) that assertions can't cover, and a structured way to generate new test scenarios.

## Decisions

- **Full command coverage** — integration tests cover all CLI commands (`source init/list/remove`, `install`, `uninstall`, `update`, `merge`, `status`, `provider add/list/remove`). *Rejected: starting with a subset — full coverage is needed to catch cross-command interaction bugs.*
- **`integration/` at repo root** — separate from `tests/` to signal different infrastructure and weight. *Rejected: `tests/integration/` — these have fundamentally different setup (wrapper script, real git) and shouldn't mix with fast unit tests.*
- **Wrapper script with subcommands** — `./integration/run.sh setup|test|teardown|shell`. Minimal responsibility: env isolation only (sets `HOME`, `XDG_CONFIG_HOME` to temp dirs). Git repo construction stays in pytest fixtures. *Rejected: three separate scripts (harder to discover), full scenario runner (over-engineered).*
- **Not in tox** — run explicitly via wrapper script. `uv run tox` stays fast for dev iterations. *Rejected: separate tox env (adds weight to tox workflow).*
- **Composable primitives + scenario presets** — small functions like `create_source_repo()`, `add_skill()`, plus preset wrappers for common scenarios. *Rejected: primitives only (too much boilerplate), presets only (not flexible enough).*
- **Typed `IntegrationEnv` dataclass** — returned by fixtures, holds all paths (home, source repo, install dir, config dir). *Rejected: plain dict (no type safety), multiple fixtures (too fragmented).*
- **Subprocess invocation only** — all CLI calls via `subprocess.run` through a wrapper that returns a result dataclass with stdout, stderr, exit_code, command, duration. *Rejected: CliRunner (misses process boundary issues).*
- **Observable outputs** — every invocation writes log files to `$ENV/logs/` AND returns result dataclass. Both always present. Designed for interactive use by agent and human.
- **QA triage skill** (`.claude/skills/qa-triage/`) — scans env directory log files (full scan or filtered). Checks: behavioral inconsistencies, output style issues, error message quality, UX flow issues. Convention-based boundary: tests assert correctness, skill reviews communication quality. Produces markdown report, then summary with batch approval for ticket creation via Tasker MCP.
- **QA test creator skill** (`.claude/skills/qa-test-creator/`) — separate from triage. Invoked standalone or chained from triage findings. Reads `integration/README.md` for available primitives/presets.
- **Flat skill structure** — two directories under `.claude/skills/`, consistent with existing `prepare-release`.

## Open questions

None.

## Out of scope

- CI integration
- GitHub Issues integration
- Performance benchmarking

## Subtasks

- [ ] [s01t0301](s01t0301-wrapper-script-and-env-scaffolding.md): Wrapper script and env scaffolding
- [ ] [s01t0302](s01t0302-integrationenv-dataclass-cli-runner-helper.md): IntegrationEnv dataclass, CLI runner helper, and log capture
- [ ] [s01t0303](s01t0303-composable-git-primitives.md): Composable git primitives
- [ ] [s01t0304](s01t0304-scenario-presets-and-first-endtoend.md): Scenario presets and first end-to-end test
- [ ] [s01t0305](s01t0305-integrationreadmemd.md): Integration/README.md
- [ ] [s01t0306](s01t0306-qa-test-creator-skill.md): QA test creator skill
- [ ] [s01t0307](s01t0307-qa-triage-skill.md): QA triage skill
- [ ] [s01t0308](s01t0308-full-command-test-coverage.md): Full command test coverage
