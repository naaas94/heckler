from __future__ import annotations

import json
import logging
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from heckler.config import HecklerConfig, apply_resolved_locale

logger = logging.getLogger(__name__)


class PersonaNotFoundError(ValueError):
    """Raised when a persona directory or its `persona.toml` is missing."""


@dataclass(frozen=True)
class Persona:
    name: str
    description: str
    system_prompt: str
    examples: list[dict[str, Any]]
    config_overrides: dict[str, Any]


# TOML section/key → HecklerConfig field (§2 mapping table; [output].comment_types excluded)
_TOML_TO_CONFIG: dict[tuple[str, str], str] = {
    ("voice", "kokoro_voice"): "kokoro_voice",
    ("voice", "kokoro_speed"): "kokoro_speed",
    ("voice", "locale"): "locale",
    ("llm", "model"): "llm_model",
    ("llm", "temperature"): "llm_temperature",
    ("llm", "max_tokens"): "llm_max_tokens",
    ("gates", "score_threshold"): "score_threshold",
    ("gates", "pacing_interval"): "min_output_interval_s",
    ("gates", "density_threshold"): "density_threshold",
    ("gates", "min_word_count"): "min_word_count",
}


def _flatten_persona_toml(raw: dict[str, Any]) -> dict[str, Any]:
    """Merge optional override sections into flat HecklerConfig keys (plus passthrough)."""
    out: dict[str, Any] = {}
    for section, table in raw.items():
        if section == "persona" or not isinstance(table, dict):
            continue
        if section not in ("voice", "llm", "gates", "output"):
            continue
        for key, value in table.items():
            mapped = _TOML_TO_CONFIG.get((section, key))
            if mapped is not None:
                out[mapped] = value
            elif section == "output" and key == "comment_types":
                # Informational only per plan §2 — not consumed as a config override.
                continue
            else:
                out[key] = value
    return out


def load_persona(persona_dir: Path) -> Persona:
    persona_dir = persona_dir.resolve()
    manifest = persona_dir / "persona.toml"
    if not persona_dir.is_dir():
        raise PersonaNotFoundError(f"Persona directory does not exist: {persona_dir}")
    if not manifest.is_file():
        raise PersonaNotFoundError(f"Missing persona.toml in {persona_dir}")

    raw = tomllib.loads(manifest.read_text(encoding="utf-8"))
    persona_meta = raw.get("persona")
    if not isinstance(persona_meta, dict):
        raise ValueError(f"persona.toml must contain a [persona] table: {manifest}")
    name = persona_meta.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"persona.toml [persona] requires non-empty string 'name': {manifest}")
    description = persona_meta.get("description", "")
    if not isinstance(description, str):
        raise ValueError(f"persona.toml [persona] 'description' must be a string if present: {manifest}")

    system_path = persona_dir / "system.md"
    if not system_path.is_file():
        raise PersonaNotFoundError(f"Missing required system.md in {persona_dir}")
    system_prompt = system_path.read_text(encoding="utf-8")

    examples_path = persona_dir / "examples.json"
    examples: list[dict[str, Any]] = []
    if examples_path.is_file():
        examples = json.loads(examples_path.read_text(encoding="utf-8"))
        if not isinstance(examples, list):
            raise ValueError(f"examples.json must be a JSON array: {examples_path}")

    config_overrides = _flatten_persona_toml(raw)
    persona = Persona(
        name=name.strip(),
        description=description,
        system_prompt=system_prompt,
        examples=examples,
        config_overrides=config_overrides,
    )
    logger.info("Loaded persona %r from %s", persona.name, persona_dir)
    return persona


def list_personas(prompts_root: Path) -> list[str]:
    prompts_root = prompts_root.resolve()
    if not prompts_root.is_dir():
        return []
    names: list[str] = []
    for child in prompts_root.iterdir():
        if child.is_dir() and (child / "persona.toml").is_file():
            names.append(child.name)
    return sorted(names)


def apply_persona_overrides(base: HecklerConfig, persona: Persona) -> HecklerConfig:
    valid_field_names = {f.name for f in fields(HecklerConfig)}
    valid_overrides: dict[str, Any] = {}
    for key, value in persona.config_overrides.items():
        if key in valid_field_names:
            valid_overrides[key] = value
        else:
            logger.warning(
                "Persona %r specifies unknown config key %r — ignored",
                persona.name,
                key,
            )
    return apply_resolved_locale(replace(base, **valid_overrides))
