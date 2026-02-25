"""YAML config loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml
from pydantic import ValidationError

from agentforge.config.defaults import merge_with_defaults
from agentforge.config.schema import ForgeConfig


class ConfigError(Exception):
    pass


class ConfigLoader:

    @staticmethod
    def load(path: Union[str, Path]) -> dict:
        path = Path(path)

        # Check file exists
        if not path.exists():
            raise ConfigError(
                f"Configuration file not found at '{path}'. "
                f"Run 'agentforge init' to create one, or specify the path with --yaml."
            )

        # Read file
        try:
            raw_text = path.read_text(encoding="utf-8")
        except PermissionError:
            raise ConfigError(f"Permission denied reading '{path}'.")
        except Exception as e:
            raise ConfigError(f"Error reading '{path}': {e}")

        # Parse YAML
        try:
            raw_config = yaml.safe_load(raw_text)
        except yaml.YAMLError as e:
            if hasattr(e, "problem_mark"):
                mark = e.problem_mark
                raise ConfigError(
                    f"YAML syntax error in '{path}' on line {mark.line + 1}, "
                    f"column {mark.column + 1}: {e.problem}"
                )
            raise ConfigError(f"YAML syntax error in '{path}': {e}")

        if not isinstance(raw_config, dict):
            raise ConfigError(
                f"Configuration file '{path}' must be a YAML mapping (dict), "
                f"got {type(raw_config).__name__}."
            )

        return ConfigLoader.validate(raw_config)

    @staticmethod
    def validate(config: dict) -> dict:
        # Merge with defaults
        merged = merge_with_defaults(config)

        # Validate with Pydantic
        try:
            validated = ForgeConfig(**merged)
        except ValidationError as e:
            errors = []
            for err in e.errors():
                loc = " \u2192 ".join(str(p) for p in err["loc"])
                msg = err["msg"]
                errors.append(f"  - {loc}: {msg}")
            error_text = "\n".join(errors)
            raise ConfigError(f"Configuration validation failed:\n{error_text}")

        # Return validated model as dict (preserves Pydantic defaults/coercions)
        return validated.model_dump()
