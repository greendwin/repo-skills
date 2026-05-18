# Agent Sandbox

A Docker-based environment for running Claude Code with persistent authentication,
a shared project workspace, and a pluggable variant system for different language stacks.

See the top-level [`README.md`](../README.md) for WSL setup and a variants overview.

## Layout

```
sandbox/
  .env.example                          template for .env (copy and edit)
  docker-compose.yml                    base compose file (variant-agnostic)
  run.sh                                one-shot: build (if needed) → up → claude
  base/
    Dockerfile                          generic dev image (ubuntu + tmux/zsh/nvim/node/claude)
    zshrc, tmux.conf                    mounted read-only into the container
  variants/
    python-uv/        Dockerfile + compose.override.yml
    python-poetry/    Dockerfile + compose.override.yml
    php/              Dockerfile + compose.override.yml
    minimal/          Dockerfile + compose.override.yml  (no language stack)
  scripts/
    build.sh     builds base image, then the active variant
    attach.sh    `tmux attach -t main`
    shell.sh     plain zsh shell
    claude.sh    `claude --dangerously-skip-permissions`
    _lib.sh      sourced helper (loads .env, sets COMPOSE_FILE)
```

## First-time setup

```bash
cd sandbox
cp .env.example .env
# Edit .env: set HOST_UID, HOST_GID, USER, COMPOSE_PROJECT_NAME, VARIANT
./run.sh
```

`run.sh` builds the base image + active variant on first invocation, starts
the container, and drops you into Claude Code. Subsequent runs skip the
build when the images already exist.

Claude credentials live in `~/.claude` / `~/.claude.json` on the host (bind-mounted
into the container), so authentication persists across container rebuilds.

## Daily usage

```bash
cd sandbox
./run.sh              # ensure running, then run claude
./scripts/attach.sh   # attach to the tmux session inside the container
./scripts/shell.sh    # plain zsh shell inside the container
./scripts/claude.sh   # another claude instance in the running container
```

The project directory (`..` relative to `sandbox/`) is mounted at `/work` inside
the container and reflects host changes in real time.

Press `Ctrl+B, D` to detach from tmux without stopping the container.

## Switching variants

```bash
# Edit VARIANT in .env, then:
docker compose down   # stop the old variant
./run.sh              # build+start the new one
```

Each variant's image is tagged `<COMPOSE_PROJECT_NAME>-<variant>:latest`, so
switching doesn't rebuild unnecessarily.

## Stopping

```bash
docker compose stop        # pause, keep state
docker compose down        # remove containers, keep volumes (auth + caches)
docker compose down -v     # nuke everything including caches and venvs
```

Named volumes owned by a variant (e.g. `venv`, `tox`, `uv-cache`, `vendor`,
`composer-cache`) live under the compose project namespace — you can list them
with `docker volume ls | grep "$COMPOSE_PROJECT_NAME"`.

## Rebuilding

After changing a `Dockerfile` or `claude_install.sh`:

```bash
./scripts/build.sh
docker compose up -d --force-recreate
```

## Adding a variant

See the top-level README's "Adding a new variant" section.
