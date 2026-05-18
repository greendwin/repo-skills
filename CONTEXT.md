# Glossary

| Term | Definition |
|------|-----------|
| **Source** | A git repository registered as a skills provider via `skills source init`. Multiple sources can coexist; each is identified by name. Auto-derived from repo directory name, overridable with `--name`. |
| **Source registry** | The collection of all registered sources, stored at `~/.config/repo-skills/sources.json`. Consulted by commands like `status`, `update`, and `merge` to locate skills across repos. |
| **Skill** | A self-contained directory containing a `SKILL.md` file, located within a source's skills root. Identified by leaf directory name regardless of nesting depth. |
| **Category** | An optional subdirectory under the skills root used to organize skills. Purely organizational — the tool identifies skills by leaf directory name, not path. |
| **Provider** | An agent platform (e.g. Claude) with a known skills install directory. Providers are registered globally in `~/.config/repo-skills/providers.json`. Claude is the built-in default. |
| **Installed copy** | A skill directory inside a provider's install path. Editable by the user — edits are merged back to the source via `skills merge`. |
| **Baseline hashes** | Per-file content hashes stored in the manifest at install/update time. Used to detect whether an installed copy has been modified without needing access to the source repo. |
