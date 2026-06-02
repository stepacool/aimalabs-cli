import json

import pytest


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Isolated config file path via AIMA_CONFIG."""
    path = tmp_path / "config.json"
    monkeypatch.setenv("AIMA_CONFIG", str(path))
    # Ensure env overrides don't leak in from the host.
    monkeypatch.delenv("AIMA_API_KEY", raising=False)
    monkeypatch.delenv("AIMA_BASE_URL", raising=False)
    monkeypatch.delenv("AIMA_OUTPUT", raising=False)
    return path


@pytest.fixture
def configured(tmp_config):
    tmp_config.write_text(
        json.dumps({"base_url": "https://api.test", "api_key": "api_secret1234"})
    )
    return tmp_config


class _Invoke:
    """Wraps CliRunner so AimaError exit codes/messages match real `main()`.

    typer.testing.CliRunner runs with standalone_mode=False, which re-raises
    ClickException instead of converting it into an exit code + stderr. In a
    real run, `aima.cli.main()` uses standalone_mode=True, so Click calls
    show() (→ stderr) and exits with `exit_code`. This helper reproduces that.
    """

    def __init__(self, runner):
        self._runner = runner

    def __call__(self, args, **kw):
        from aima.cli import app
        from aima.errors import AimaError

        result = self._runner.invoke(app, args, **kw)
        exc = result.exception
        if isinstance(exc, AimaError):
            result.aima_exit = exc.exit_code
            result.aima_stderr = exc.message
        else:
            result.aima_exit = result.exit_code
            result.aima_stderr = getattr(result, "stderr", "") or ""
        return result


@pytest.fixture
def runner():
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def cli(runner):
    return _Invoke(runner)
