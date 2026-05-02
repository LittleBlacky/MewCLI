"""Config manager."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional


ENV_MAPPING = {
    "MINICODE_PROVIDER": "model.provider",
    "MINICODE_API_KEY": "model.api_key",
}


class ConfigManager:
    """Unified configuration management."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".minicode" / "config.json"
        self._config = self._load()

    def _load(self) -> dict:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self._default_config()

    def _default_config(self) -> dict:
        return {
            "model": {"provider": "anthropic", "model": "claude-sonnet-4-7"},
            "permissions": {"mode": "default"},
            "storage": {"dir": str(Path.home() / ".minicode")},
            "features": {"auto_compact": True, "team_enabled": False, "skills_enabled": True},
        }

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def get_model_config(self) -> dict:
        return {
            "provider": self.get("model.provider", "anthropic"),
            "model": self.get("model.model", "claude-sonnet-4-7"),
            "api_key": self.get("model.api_key") or os.environ.get("MINICODE_API_KEY"),
            "base_url": self.get("model.base_url"),
        }

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save()

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self._config, indent=2), encoding="utf-8")

    def reload(self) -> None:
        self._config = self._load()


_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager


def reset_config_manager() -> None:
    global _config_manager
    _config_manager = None