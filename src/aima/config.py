"""Configuration: load/save ~/.aima/config.json with env overrides.

Resolution order for each value:
  1. Environment variable (AIMA_API_KEY / AIMA_BASE_URL)
  2. config file
  3. built-in default (base_url only)

The config file path itself can be relocated with AIMA_CONFIG.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

DEFAULT_BASE_URL = "https://api.aimalabs.io"

_KNOWN_KEYS = ("base_url", "api_key")


def config_path() -> Path:
    """Resolve the config file path, honoring AIMA_CONFIG."""
    override = os.environ.get("AIMA_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".aima" / "config.json"


def _read_file() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Cannot read config at {path}: {exc}") from exc
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config at {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config at {path} must be a JSON object.")
    return data


@dataclass
class Config:
    """Effective configuration after merging env overrides over the file."""

    base_url: str
    api_key: str | None
    source_path: Path

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def masked_api_key(self) -> str:
        """Render the api_key as `api_…<last 4>` (or a placeholder)."""
        return mask_api_key(self.api_key)


def mask_api_key(api_key: str | None) -> str:
    if not api_key:
        return "(not set)"
    if len(api_key) <= 4:
        return "api_…" + api_key
    return "api_…" + api_key[-4:]


def load_config() -> Config:
    """Build the effective Config from file + environment overrides."""
    file_data = _read_file()

    base_url = (
        os.environ.get("AIMA_BASE_URL")
        or file_data.get("base_url")
        or DEFAULT_BASE_URL
    ).rstrip("/")

    api_key = os.environ.get("AIMA_API_KEY") or file_data.get("api_key") or None

    return Config(base_url=base_url, api_key=api_key, source_path=config_path())


def save_config(*, base_url: str | None = None, api_key: str | None = None) -> Path:
    """Write the config file (mode 0600), merging with what's already there.

    Only the keys passed in are updated; existing values are preserved.
    Returns the path written.
    """
    path = config_path()
    data = _read_file()

    if base_url is not None:
        data["base_url"] = base_url.rstrip("/")
    if api_key is not None:
        data["api_key"] = api_key

    path.parent.mkdir(parents=True, exist_ok=True)
    # Write then chmod, so the secret is never world-readable mid-write.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    os.replace(tmp, path)
    return path


def set_key(key: str, value: str) -> Path:
    """Set a single config key (base_url or api_key)."""
    if key not in _KNOWN_KEYS:
        raise ConfigError(
            f"Unknown config key '{key}'. Valid keys: {', '.join(_KNOWN_KEYS)}."
        )
    return save_config(**{key: value})


def clear_config() -> Path | None:
    """Delete the config file. Returns the path if one existed, else None."""
    path = config_path()
    if path.exists():
        path.unlink()
        return path
    return None


def file_contents_for_show() -> dict:
    """Raw file contents (no env merge) for `config show`."""
    return _read_file()
