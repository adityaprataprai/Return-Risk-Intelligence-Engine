import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv

# Load .env file automatically if present
load_dotenv()


class Config:
    """Configuration manager that loads YAML files and merges environment overrides."""

    def __init__(self, config_name: str, config_dir: Optional[str] = None):
        self.config_name = config_name
        self.config_dir = Path(
            config_dir or os.getenv("CONFIG_DIR", Path(__file__).resolve().parent.parent.parent / "config")
        )
        self._data: Dict[str, Any] = self._load_yaml()
        self._apply_env_overrides()

    def _load_yaml(self) -> Dict[str, Any]:
        """Loads YAML configuration file."""
        file_path = self.config_name
        if not file_path.endswith((".yaml", ".yml")):
            file_path = f"{file_path}.yaml"

        full_path = self.config_dir / file_path
        if not full_path.exists():
            return {}

        with open(full_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            return content if isinstance(content, dict) else {}

    def _apply_env_overrides(self) -> None:
        """Applies environment variable overrides where applicable."""
        # Check standard config prefix overrides, e.g. CONFIG__POPULATION__NUM_CUSTOMERS
        prefix = f"CONFIG_{self.config_name.replace('/', '_').replace('-', '_').upper()}_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                sub_key = key[len(prefix) :].lower().replace("__", ".")
                self._set_nested(sub_key, self._cast_value(value))

    def _cast_value(self, val: str) -> Any:
        """Helper to cast environment string variables into appropriate primitive types."""
        if val.lower() in ("true", "yes", "1"):
            return True
        if val.lower() in ("false", "no", "0"):
            return False
        try:
            return int(val)
        except ValueError:
            pass
        try:
            return float(val)
        except ValueError:
            pass
        return val

    def _set_nested(self, key_path: str, value: Any) -> None:
        """Sets a value in nested dictionary using dot notation."""
        parts = key_path.split(".")
        d = self._data
        for part in parts[:-1]:
            if part not in d or not isinstance(d[part], dict):
                d[part] = {}
            d = d[part]
        d[parts[-1]] = value

    def get(self, key_path: Optional[str] = None, default: Any = None) -> Any:
        """Fetches value from configuration using dot notation.
        If key_path is None, returns the entire configuration dict.
        """
        if not key_path:
            return self._data

        keys = key_path.split(".")
        val: Any = self._data
        for key in keys:
            if isinstance(val, dict) and key in val:
                val = val[key]
            else:
                return default
        return val

    def to_dict(self) -> Dict[str, Any]:
        """Returns the full config data as a dictionary."""
        return self._data

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(f"Configuration key '{key}' not found in {self.config_name}")
        return val

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None
