from importlib.metadata import version

from pytest_subtests import SubTests

from tests.cli.helper import InvokeResult, NoopResult, assert_invoke


def test_version_flag() -> None:
    result = assert_invoke("--version")
    assert isinstance(result, NoopResult)
    assert version("repo-skills") in result.output


def test_help_lists_all_commands() -> None:
    result = assert_invoke("--help")
    assert isinstance(result, InvokeResult)
    for cmd in ("install", "update", "uninstall", "source"):
        assert cmd in result.output


COMMANDS = ("install", "update", "uninstall", "source")


def test_each_subcommand_has_help(subtests: SubTests) -> None:
    for cmd in COMMANDS:
        with subtests.test(cmd=cmd):
            assert_invoke(cmd, "--help")
