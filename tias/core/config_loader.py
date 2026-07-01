import json
import os
from typing import Any, Dict

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


def load_config(config_path: str) -> Dict[str, Any]:
    _, ext = os.path.splitext(config_path.lower())
    with open(config_path, "rb") as config_file:
        if ext == ".toml":
            return tomllib.load(config_file)
        if ext == ".json":
            return json.load(config_file)

    raise ValueError(f"Unsupported config file format: {config_path}")
