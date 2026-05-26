# Glossary

| Term | Definition |
|------|-----------|
| **Source** | A git repository registered as a skills provider via `skills source init`. Multiple sources can coexist; each is identified by name. Auto-derived from repo directory name, overridable with `--name`. |
| **Source registry** | The collection of all registered sources, stored at `~/.config/repo-skills/sources.json`. Consulted by commands like `status`, `update`, and `merge` to locate skills across repos. |
| **Skill** | A self-contained directory containing a `SKILL.md` file, located within a source's skills root. Identified by leaf directory name regardless of nesting depth. |
| **Category** | An optional subdirectory under the skills root used to organize skills. Purely organizational — the tool identifies skills by leaf directory name, not path. |
| **Provider** | An agent platform (e.g. Claude) with a known skills install directory. Providers are registered globally in `~/.config/repo-skills/providers.json`. Claude is included as a default on first creation; the user may remove or modify it freely. |
| **Installed copy** | A skill directory inside a provider's install path. Editable by the user — edits are merged back to the source via `skills merge`. |
| **Baseline hashes** | Per-file content hashes stored in the manifest at install/update time. Used to detect whether an installed copy has been modified without needing access to the source repo. |
| **Available skill** | A skill present in a registered source but not yet installed (not in the manifest). Shown by `skills status` so the user knows what can be installed. |
| **Orphan skill** | A directory inside a provider's install path that is not tracked in the manifest and does not match any skill in a registered source. Likely placed there manually. |
| **Mergeable skill** | A directory inside a provider's install path that is not tracked in the manifest but matches a skill name in a registered source. Can be brought under management via `skills install --force`. |
| **Pinned branch** | The branch captured at `source init` time that merge and other write operations target. Defaults to the current branch when `source init` runs. Replaces the need for `--any-branch`. |
| **Detached skill** | An installed skill whose stored commit is no longer reachable from the pinned branch. Detected by `skills update`; the manifest entry is preserved (with a `detached` flag) so tracking can resume automatically if the commit becomes reachable again. Displayed as mergeable or orphan by `skills status`. |
