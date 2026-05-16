## Development

* On any development iteration, the final step is to run `uv run tox` (all environments).
* Always fix **all** reported `tox` issues including **pre-existing**.
* Never include tasks IDs into code comments (e.g. `s12t03`, `s01` in section headers or inline comments).
* When finishing a task change its status to `in-review` by MCP tool `review_task`.

## Python Guide

* Never use `type: ignore` if it can be fixed normally.
* Never use `unittest.mock.patch`, use `monkeypatch`.
* Never use inline imports inside methods and tests.
* Always use `assert_invoke` helper instead of `CliRunner`.