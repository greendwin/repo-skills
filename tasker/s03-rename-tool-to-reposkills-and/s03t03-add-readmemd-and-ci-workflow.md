---
id: s03t03
slug: add-readmemd-and-ci-workflow
status: pending
---

# Add README.md and CI workflow

**Goal:** Minimal README with project name, one-line description, usage basics (install, update, list, uninstall). GitHub Actions workflow (`.github/workflows/ci.yml`) that runs `uv run tox` on push/PR to main, matrix across Python 3.10–3.14, matching the mcp-tasker pattern.

**Decisions:**
- Add minimal README.md
- GitHub repo: https://github.com/greendwin/repo-skills

**Key files:** `README.md` (new), `.github/workflows/ci.yml` (new)
