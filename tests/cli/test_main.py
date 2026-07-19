from click.testing import CliRunner
from eattoken.cli.main import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "probe" in result.output
    assert "run" in result.output


def test_probe_requires_model():
    runner = CliRunner()
    result = runner.invoke(cli, ["probe", "--api-url", "http://x", "--api-key", "k", "--provider", "openai"])
    assert result.exit_code != 0
    assert "model" in result.output.lower()
