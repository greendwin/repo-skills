# repo-skills

[![tests](https://github.com/greendwin/repo-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/greendwin/repo-skills/actions/workflows/ci.yml)

CLI tool for managing [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills from a shared repository.

## Install

```bash
uv tool install git+https://github.com/greendwin/repo-skills.git
```

## Usage

Run from within a git repo that has a `skills/` directory:

```bash
skills list                # show available and installed skills
skills install <name>      # install a skill from the repo
skills update              # update all installed skills
skills update <name>       # update a specific skill
skills uninstall <name>    # remove an installed skill
```

## License

[MIT](LICENSE)
