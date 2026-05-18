---
id: s03
slug: rename-tool-to-reposkills-and
status: pending
---

# Rename tool to repo-skills and move to github

## Decisions

- **Distribution name → `repo-skills`** — clean rebrand matching the GitHub repo name
- **Python package → `repo_skills`** — PEP 8 convention for the distribution name; avoids mismatch between repo and imports
- **CLI entry point → `skills`** — short and ergonomic for daily use
- **Manifest filename → `.skills-manifest.json`** — clean break with no existing users to migrate; reads better
- **Discovery dir stays `skills/`** — describes the content, not the tool
- **Install dir stays `~/.claude/skills/`** — standard Claude Code location, changing would break integration
- **Tasker files untouched** — historical records, not code
- **Add minimal README.md** — project name, one-line description, install/usage basics
- **pyproject.toml metadata** — add author `Evgeniy A. Cymbalyuk <cimbaluk@gmail.com>`, project URL `https://github.com/greendwin/repo-skills`, license link
- **GitHub repo** — `https://github.com/greendwin/repo-skills`

## Subtasks

- [x] [s03t01](s03t01-rename-package-and-update-all.md): Rename package and update all imports
- [ ] [s03t02](s03t02-rename-manifest-file.md): Rename manifest file
- [ ] [s03t03](s03t03-add-readmemd-and-ci-workflow.md): Add README.md and CI workflow
