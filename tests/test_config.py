import os
import stat

from aima import config as cfg


def test_save_sets_0600(tmp_config):
    path = cfg.save_config(base_url="https://api.test", api_key="api_abcd1234")
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


def test_env_overrides_file(configured, monkeypatch):
    monkeypatch.setenv("AIMA_API_KEY", "api_fromenv")
    monkeypatch.setenv("AIMA_BASE_URL", "https://env.example/")
    conf = cfg.load_config()
    assert conf.api_key == "api_fromenv"
    # trailing slash stripped
    assert conf.base_url == "https://env.example"


def test_default_base_url(tmp_config):
    conf = cfg.load_config()
    assert conf.base_url == cfg.DEFAULT_BASE_URL
    assert conf.api_key is None
    assert conf.has_api_key is False


def test_mask():
    assert cfg.mask_api_key("api_secret9999") == "api_…9999"
    assert cfg.mask_api_key(None) == "(not set)"


def test_set_unknown_key(tmp_config):
    import pytest

    from aima.errors import ConfigError

    with pytest.raises(ConfigError):
        cfg.set_key("nonsense", "x")


def test_clear(configured):
    assert cfg.clear_config() == configured
    assert cfg.clear_config() is None
