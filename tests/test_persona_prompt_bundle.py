"""Regression guards for the shipped `prompts/heckler/` persona bundle (T2 migration)."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE = REPO_ROOT / "prompts" / "heckler"


def test_heckler_prompt_bundle_files_exist() -> None:
    assert (BUNDLE / "system.md").is_file()
    assert (BUNDLE / "examples.json").is_file()
    assert (BUNDLE / "persona.toml").is_file()


def test_root_level_prompt_assets_removed() -> None:
    assert not (REPO_ROOT / "prompts" / "system.md").exists()
    assert not (REPO_ROOT / "prompts" / "examples.json").exists()


def test_persona_toml_parses_and_maps_contract_sections() -> None:
    raw = (BUNDLE / "persona.toml").read_text(encoding="utf-8")
    data = tomllib.loads(raw)
    persona = data.get("persona", {})
    assert persona.get("name") == "Heckler"
    assert persona.get("description") == "Dry deadpan commentator"
    assert data["voice"]["kokoro_voice"] == "af_sarah"
    assert data["voice"]["kokoro_speed"] == pytest.approx(1.05)
    assert data["llm"]["model"] == "openai/gpt-4o-mini"
    assert data["llm"]["temperature"] == pytest.approx(0.9)
    assert data["llm"]["max_tokens"] == 150
    assert data["gates"]["score_threshold"] == pytest.approx(0.65)
    assert data["gates"]["pacing_interval"] == pytest.approx(12.0)
    assert data["gates"]["density_threshold"] == pytest.approx(0.40)
    assert data["gates"]["min_word_count"] == 4
    assert "output" not in data


def test_examples_json_is_non_empty_list_of_objects() -> None:
    examples = json.loads((BUNDLE / "examples.json").read_text(encoding="utf-8"))
    assert isinstance(examples, list)
    assert len(examples) > 0
    assert all(isinstance(item, dict) for item in examples)


def test_system_prompt_non_empty() -> None:
    text = (BUNDLE / "system.md").read_text(encoding="utf-8")
    assert text.strip()
