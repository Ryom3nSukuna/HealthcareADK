from pathlib import Path

import yaml

_CONFIG_DIR = Path(__file__).parent / "config"


def load_config(name: str) -> dict:
    with open(_CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)
