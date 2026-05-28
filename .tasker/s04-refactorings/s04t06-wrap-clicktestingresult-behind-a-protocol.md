---
id: s04t06
slug: wrap-clicktestingresult-behind-a-protocol
status: done
---

# Wrap click.testing.Result behind a protocol in test helper

Test-infra decoupling (not a CLI bug). Low priority.

`tests/cli/helper.py`:
> TODO: rework `click.testing.Result` to protocol to get rid of click dependency

Define a protocol for the result type returned by the `assert_invoke` helper so tests no longer depend on `click.testing.Result` directly. Remove the TODO once done.
