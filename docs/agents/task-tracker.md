# Task tracker

This repo's task tracker is the **tasker MCP server**. Tasks live inside tasker
and are reached through its MCP tools (the `mcp__tasker__*` functions). Each task
has a short id (e.g. `s01t03`). Hierarchy is native: a task may have a parent and
its own subtasks. This document tells skills how to perform each task-tracker
operation against tasker. It is self-contained.

## Verbs

### `create-task`

Call `mcp__tasker__create_task` with a `title` and a `description`. Omit `parent`
for a top-level task. Tasker returns the new task's id — report it to the caller.

### `read-task`

Call `mcp__tasker__view_tasks` with `task_refs: [<id>]`. It returns the task's
title, status, description, and the ids of its subtasks.

### `update-task`

Call `mcp__tasker__edit_task` with `task_ref: <id>` and the `title` and/or
`description` to change. Do not change status here — use `set-status`.

### `list-tasks`

Call `mcp__tasker__list_tasks` to enumerate tasks with their ids, titles, and
statuses. For a single subtree, `mcp__tasker__view_tasks` on a parent id returns
its subtask ids.

### `create-subtask`

Call `mcp__tasker__create_task` with `parent: <parent-id>` (plus `title` and
`description`). This uses tasker's native parent/child relation — no emulation is
needed. Tasker returns the subtask's id.

### `set-status`

Move the task to a status role's native state by calling the matching lifecycle
tool from the table below, with `task_ref: <id>`.

## Status roles

Each canonical status role maps to a tasker lifecycle transition and the resulting
native status.

| Status role     | Native transition (tool)         | Resulting tasker status |
| --------------- | -------------------------------- | ----------------------- |
| `pending`       | `mcp__tasker__reset_task`        | `pending`               |
| `in-progress`   | `mcp__tasker__start_task`        | `in-progress`           |
| `in-review`     | `mcp__tasker__review_task`       | `in-review`             |
| `done`          | `mcp__tasker__finish_task`       | `done`                  |
