# repo-skills

[![tests](https://github.com/greendwin/repo-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/greendwin/repo-skills/actions/workflows/ci.yml)

CLI tool for managing [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills from a shared repository.

Keep your team's skills in a central git repo, install them into any provider (Claude Code by default), edit freely, and merge changes back — all from the command line.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended for installation)

## Install

```bash
uv tool install git+https://github.com/greendwin/repo-skills.git
```

Verify the installation:

```bash
skills --version
```

## Quick start

### 1. Register a skills source

Navigate to a git repository that contains a `skills/` directory and register it:

```bash
cd /path/to/your-skills-repo
skills source init
```

This registers the current repo as a skill source, pinned to the current branch. You can override the name and branch:

```bash
skills source init --name my-team --branch main
```

### 2. Check available skills

```bash
skills status
```

This shows installed skills, available skills from registered sources, and any untracked (orphan) skill directories.

### 3. Install skills

```bash
skills install my-skill
skills install skill-a skill-b skill-c
```

When multiple sources are registered, specify which one:

```bash
skills install my-skill -s my-team
```

### 4. Update skills

Pull the latest version from the source:

```bash
skills update              # update all installed skills
skills update my-skill     # update a specific skill
```

### 5. Merge local edits back

If you edit an installed skill (e.g. Claude refines it while working), push those changes back to the source repo:

```bash
skills merge               # merge all modified skills
skills merge my-skill      # merge a specific skill
```

The merge creates a commit in the source repo. Use `--no-commit` to stage changes without committing, or `--abort` / `--continue` to manage an in-progress merge.

### 6. Uninstall

```bash
skills uninstall my-skill
skills uninstall skill-a skill-b
```

## Concepts

| Term | Description |
|------|-------------|
| **Source** | A git repo registered via `skills source init`. Contains a `skills/` directory with one or more skills. Multiple sources can coexist. |
| **Skill** | A directory containing a `SKILL.md` file inside a source's `skills/` tree. Identified by leaf directory name, regardless of nesting depth. |
| **Provider** | An agent platform with a known skills install directory. Claude Code is the built-in default. |
| **Installed copy** | A skill directory inside a provider's install path, editable by the user. |
| **Pinned branch** | The branch captured at `source init` time. Merge and write operations target this branch. |

## Commands

### `skills source`

Manage skill sources (git repositories).

```bash
skills source init             # register current repo as a source
skills source init --name foo  # custom source name
skills source init --branch dev  # pin to a specific branch
skills source list             # list all registered sources
skills source remove <name>    # unregister a source
```

### `skills provider`

Manage providers (agent platforms). Claude Code is registered by default.

```bash
skills provider list                         # list registered providers
skills provider add <name> --install-dir /path/to/skills  # register a new provider
skills provider remove <name>                # unregister a provider
```

### `skills install`

```bash
skills install <name> [<name> ...]   # install one or more skills
skills install <name> -s <source>    # from a specific source
skills install <name> --force        # overwrite existing skill
skills install <name> --offline      # skip git pull
```

### `skills update`

```bash
skills update            # update all installed skills
skills update <name>     # update a specific skill
skills update --offline  # skip git pull
```

### `skills uninstall`

```bash
skills uninstall <name> [<name> ...]
```

### `skills merge`

Merge provider-side edits back into the source repo.

```bash
skills merge               # merge all modified skills
skills merge <name>        # merge a specific skill
skills merge --from <provider>  # specify provider (when ambiguous)
skills merge --no-commit   # stage changes without committing
skills merge --continue    # finalize an in-progress merge
skills merge --abort       # abort an in-progress merge
skills merge --offline     # skip git pull
```

### `skills status`

```bash
skills status          # show status of all skills
skills status --sync   # pull source repos before checking
```

### Global options

```bash
skills --version    # show version
skills --debug      # show full traceback on errors
```

## Skill directory structure

A source repository organizes skills under a `skills/` root:

```
your-skills-repo/
  skills/
    my-skill/
      SKILL.md
      ...
    category/
      another-skill/
        SKILL.md
        ...
```

Categories (subdirectories) are purely organizational — the tool identifies skills by their leaf directory name.

## Configuration

Configuration files are stored in `~/.config/repo-skills/`:

- `sources.json` — registered skill sources
- `providers.json` — registered providers

## License

[MIT](LICENSE)

## Release Notes

### v0.2.0

- Multi-source architecture: register skill sources (`source init/list/remove`), pin to a branch
- Provider management: add, list, and remove agent platforms (Claude Code built-in)
- Install, update, and uninstall skills across sources and providers
- `skills merge` — push provider-side edits back to source repos with `--continue`, `--abort`, `--no-commit`
- `skills status` — installed, available, orphan, and mergeable skills at a glance
- `--version` and `--debug` global flags
- Short flags (`-s`, `-f`) for install; multi-skill install/uninstall
- Offline mode (`--offline`) for all network operations
- Pretty error reporting with structured CLI output styling

### v0.1.0

- Initial release
