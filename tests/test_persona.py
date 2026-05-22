from __future__ import annotations

import json
import logging
import textwrap
import tomllib
from pathlib import Path
from typing import Any

import pytest

from heckler.config import HecklerConfig
from heckler.locale import UnsupportedLocaleError
from heckler.persona import (
    Persona,
    PersonaNotFoundError,
    apply_persona_overrides,
    load_persona,
    list_personas,
)


def test_persona_construction() -> None:
    p = Persona(
        name="x",
        description="d",
        system_prompt="sys",
        examples=[{"type": "sarcasm", "comment": "hi", "score": 0.9}],
        config_overrides={"llm_model": "openai/gpt-4o"},
    )
    assert p.name == "x"
    assert p.description == "d"
    assert p.system_prompt == "sys"
    assert p.examples[0]["type"] == "sarcasm"
    assert p.config_overrides["llm_model"] == "openai/gpt-4o"


def _write_minimal_persona(
    root: Path,
    *,
    name: str = "Test",
    description: str = "Desc",
    system: str = "You are a test.",
    examples: list[dict] | None = None,
    extra_toml: str = "",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    ex = examples if examples is not None else [{"type": "observation", "comment": "c", "score": 0.8}]
    (root / "system.md").write_text(system, encoding="utf-8")
    (root / "examples.json").write_text(json.dumps(ex), encoding="utf-8")
    toml = textwrap.dedent(
        f"""
        [persona]
        name = {json.dumps(name)}
        description = {json.dumps(description)}
        {extra_toml}
        """
    ).lstrip()
    (root / "persona.toml").write_text(toml, encoding="utf-8")
    return root


def test_load_persona_happy_path(tmp_path, caplog) -> None:
    caplog.set_level(logging.INFO)
    d = tmp_path / "alpha"
    _write_minimal_persona(d, name="Alpha", system="SYSBODY")
    p = load_persona(d)
    assert p.name == "Alpha"
    assert p.description == "Desc"
    assert p.system_prompt == "SYSBODY"
    assert len(p.examples) == 1
    assert "Loaded persona 'Alpha'" in caplog.text


def test_load_persona_without_examples_json(tmp_path) -> None:
    d = tmp_path / "bare"
    d.mkdir()
    (d / "system.md").write_text("s", encoding="utf-8")
    (d / "persona.toml").write_text(
        '[persona]\nname = "Bare"\ndescription = ""\n',
        encoding="utf-8",
    )
    p = load_persona(d)
    assert p.examples == []


def test_load_persona_flattens_mapped_toml_keys(tmp_path) -> None:
    d = tmp_path / "mapped"
    d.mkdir()
    (d / "system.md").write_text("x", encoding="utf-8")
    (d / "persona.toml").write_text(
        textwrap.dedent(
            """
            [persona]
            name = "M"
            description = ""

            [llm]
            model = "openai/gpt-test"
            temperature = 0.1
            max_tokens = 99

            [gates]
            pacing_interval = 3.0
            score_threshold = 0.5

            [voice]
            kokoro_voice = "af_test"
            kokoro_speed = 1.2
            """
        ).strip(),
        encoding="utf-8",
    )
    p = load_persona(d)
    assert p.config_overrides == {
        "llm_model": "openai/gpt-test",
        "llm_temperature": 0.1,
        "llm_max_tokens": 99,
        "min_output_interval_s": 3.0,
        "score_threshold": 0.5,
        "kokoro_voice": "af_test",
        "kokoro_speed": 1.2,
    }


def test_load_persona_skips_output_comment_types(tmp_path) -> None:
    d = tmp_path / "outsec"
    d.mkdir()
    (d / "system.md").write_text("x", encoding="utf-8")
    (d / "persona.toml").write_text(
        textwrap.dedent(
            """
            [persona]
            name = "O"
            description = ""

            [output]
            comment_types = ["sarcasm"]
            """
        ).strip(),
        encoding="utf-8",
    )
    p = load_persona(d)
    assert "comment_types" not in p.config_overrides


def test_load_persona_passthrough_unknown_key_in_section(tmp_path, caplog) -> None:
    d = tmp_path / "passthrough"
    d.mkdir()
    (d / "system.md").write_text("x", encoding="utf-8")
    (d / "persona.toml").write_text(
        textwrap.dedent(
            """
            [persona]
            name = "P"
            description = ""

            [llm]
            future_key = 123
            model = "openai/gpt-4o-mini"
            """
        ).strip(),
        encoding="utf-8",
    )
    p = load_persona(d)
    assert p.config_overrides["future_key"] == 123
    assert p.config_overrides["llm_model"] == "openai/gpt-4o-mini"
    base = HecklerConfig()
    caplog.set_level(logging.WARNING)
    apply_persona_overrides(base, p)
    assert "unknown config key 'future_key'" in caplog.text


def test_load_persona_missing_directory_raises(tmp_path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(PersonaNotFoundError, match="does not exist"):
        load_persona(missing)


def test_load_persona_missing_persona_toml_raises(tmp_path) -> None:
    d = tmp_path / "empty_dir"
    d.mkdir()
    with pytest.raises(PersonaNotFoundError, match="Missing persona.toml"):
        load_persona(d)


def test_load_persona_missing_system_md_raises(tmp_path) -> None:
    d = tmp_path / "no_system"
    d.mkdir()
    (d / "persona.toml").write_text('[persona]\nname = "N"\ndescription = ""\n', encoding="utf-8")
    with pytest.raises(PersonaNotFoundError, match="system.md"):
        load_persona(d)


def test_load_persona_invalid_toml_raises(tmp_path) -> None:
    d = tmp_path / "bad_toml"
    d.mkdir()
    (d / "system.md").write_text("x", encoding="utf-8")
    (d / "persona.toml").write_text("this is not valid toml [[[", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        load_persona(d)


def test_load_persona_missing_persona_section_raises(tmp_path) -> None:
    d = tmp_path / "no_persona_table"
    d.mkdir()
    (d / "system.md").write_text("x", encoding="utf-8")
    (d / "persona.toml").write_text("[voice]\nkokoro_voice = 'a'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="\\[persona\\]"):
        load_persona(d)


def test_load_persona_examples_not_array_raises(tmp_path) -> None:
    d = tmp_path / "bad_examples"
    d.mkdir()
    (d / "system.md").write_text("x", encoding="utf-8")
    (d / "examples.json").write_text('"string"', encoding="utf-8")
    (d / "persona.toml").write_text('[persona]\nname = "E"\ndescription = ""\n', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        load_persona(d)


def test_list_personas_sorted_and_filters(tmp_path) -> None:
    root = tmp_path / "prompts"
    root.mkdir()
    z = root / "zebra"
    _write_minimal_persona(z, name="Z")
    a = root / "aaa"
    _write_minimal_persona(a, name="A")
    (root / "no_manifest").mkdir()
    (root / "no_manifest" / "system.md").write_text("x", encoding="utf-8")
    assert list_personas(root) == ["aaa", "zebra"]


def test_list_personas_missing_root_returns_empty(tmp_path) -> None:
    assert list_personas(tmp_path / "missing_prompts") == []


def test_load_persona_flattens_voice_locale(tmp_path) -> None:
    d = tmp_path / "es_voice"
    d.mkdir()
    (d / "system.md").write_text("x", encoding="utf-8")
    (d / "persona.toml").write_text(
        textwrap.dedent(
            """
            [persona]
            name = "Es"
            description = ""

            [voice]
            locale = "es"
            """
        ).strip(),
        encoding="utf-8",
    )
    p = load_persona(d)
    assert p.config_overrides == {"locale": "es"}


def test_apply_persona_overrides_resolves_spanish_locale(tmp_path) -> None:
    d = tmp_path / "es_merge"
    _write_minimal_persona(
        d,
        extra_toml=textwrap.dedent(
            """
            [voice]
            locale = "es"
            """
        ),
    )
    p = load_persona(d)
    base = HecklerConfig(locale="en", whisper_language="en", kokoro_lang_code="a")
    merged = apply_persona_overrides(base, p)
    assert merged.locale == "es"
    assert merged.whisper_language == "es"
    assert merged.kokoro_lang_code == "e"


def test_apply_persona_overrides_rejects_unknown_locale(tmp_path) -> None:
    d = tmp_path / "bad_locale"
    _write_minimal_persona(
        d,
        extra_toml=textwrap.dedent(
            """
            [voice]
            locale = "xx"
            """
        ),
    )
    p = load_persona(d)
    with pytest.raises(UnsupportedLocaleError):
        apply_persona_overrides(HecklerConfig(), p)


def test_apply_persona_overrides_applies_known_fields(tmp_path) -> None:
    d = tmp_path / "ov"
    _write_minimal_persona(
        d,
        extra_toml=textwrap.dedent(
            """
            [llm]
            model = "openai/custom"
            temperature = 0.42
            """
        ),
    )
    p = load_persona(d)
    base = HecklerConfig(llm_model="openai/gpt-4o-mini", llm_temperature=0.9)
    merged = apply_persona_overrides(base, p)
    assert merged.llm_model == "openai/custom"
    assert merged.llm_temperature == 0.42
    assert merged is not base


def test_apply_persona_overrides_warns_on_unknown_keys(tmp_path, caplog) -> None:
    d = tmp_path / "unk"
    _write_minimal_persona(
        d,
        extra_toml=textwrap.dedent(
            """
            [llm]
            not_a_field = true
            model = "openai/gpt-4o-mini"
            """
        ),
    )
    p = load_persona(d)
    caplog.set_level(logging.WARNING)
    merged = apply_persona_overrides(HecklerConfig(), p)
    assert merged.llm_model == "openai/gpt-4o-mini"
    assert "unknown config key 'not_a_field'" in caplog.text


def test_apply_persona_overrides_empty_overrides_returns_copy(tmp_path) -> None:
    d = tmp_path / "no_ov"
    _write_minimal_persona(d, extra_toml="")
    p = load_persona(d)
    assert p.config_overrides == {}
    base = HecklerConfig(score_threshold=0.7)
    merged = apply_persona_overrides(base, p)
    assert merged == base
    assert merged is not base


def test_apply_persona_overrides_each_mapping_table_field(tmp_path) -> None:
    """Kill-criterion guard: every §2 TOML mapping target must exist on HecklerConfig."""
    d = tmp_path / "allmap"
    d.mkdir()
    (d / "system.md").write_text("s", encoding="utf-8")
    (d / "persona.toml").write_text(
        textwrap.dedent(
            """
            [persona]
            name = "All"
            description = ""

            [voice]
            kokoro_voice = "af_x"
            kokoro_speed = 1.11
            locale = "es"

            [llm]
            model = "openai/m"
            temperature = 0.22
            max_tokens = 33

            [gates]
            score_threshold = 0.44
            pacing_interval = 5.5
            density_threshold = 0.55
            min_word_count = 6
            """
        ).strip(),
        encoding="utf-8",
    )
    p = load_persona(d)
    base = HecklerConfig()
    merged = apply_persona_overrides(base, p)
    assert merged.locale == "es"
    assert merged.whisper_language == "es"
    assert merged.kokoro_lang_code == "e"
    assert merged.kokoro_voice == "af_x"
    assert merged.kokoro_speed == 1.11
    assert merged.llm_model == "openai/m"
    assert merged.llm_temperature == 0.22
    assert merged.llm_max_tokens == 33
    assert merged.score_threshold == 0.44
    assert merged.min_output_interval_s == 5.5
    assert merged.density_threshold == 0.55
    assert merged.min_word_count == 6
