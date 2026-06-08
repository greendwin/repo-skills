---
id: s10t0108
slug: rework-cli-from-click-to
status: done
---

# Rework CLI from click to typer + typer_di

Replace click with typer and typer_di to eliminate duplicated option boilerplate (`--repo-skills-dir`, `--install-dir`, `--manifest-path`) across commands. Use dependency injection to resolve shared parameters like `find_repo_skills_dir()` once.
