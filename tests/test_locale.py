import pytest

from heckler.config import HecklerConfig, apply_resolved_locale
from heckler.locale import (
    SUPPORTED_LOCALES,
    LocaleProfile,
    UnsupportedLocaleError,
    normalize_locale,
    resolve_locale,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("en", "en"),
        ("  EN-US  ", "en-us"),
        ("ES", "es"),
    ],
)
def test_normalize_locale_strip_and_lower(raw: str, expected: str) -> None:
    assert normalize_locale(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\t"])
def test_normalize_locale_empty_raises(raw: str) -> None:
    with pytest.raises(UnsupportedLocaleError):
        normalize_locale(raw)


@pytest.mark.parametrize(
    ("locale", "profile"),
    [
        ("en", LocaleProfile("en", "a")),
        ("en-us", LocaleProfile("en", "a")),
        ("en-gb", LocaleProfile("en", "b")),
        ("es", LocaleProfile("es", "e")),
    ],
)
def test_resolve_locale_supported_keys(locale: str, profile: LocaleProfile) -> None:
    assert resolve_locale(locale) == profile
    assert resolve_locale(f"  {locale.upper()}  ") == profile


def test_resolve_locale_unknown_raises_not_english_fallback() -> None:
    with pytest.raises(UnsupportedLocaleError):
        resolve_locale("fr")


def test_supported_locales_includes_en_and_es() -> None:
    assert "en" in SUPPORTED_LOCALES
    assert "es" in SUPPORTED_LOCALES
    assert SUPPORTED_LOCALES["en"].whisper_language == "en"
    assert SUPPORTED_LOCALES["es"].kokoro_lang_code == "e"


def test_apply_resolved_locale_sets_derived_fields() -> None:
    cfg = HecklerConfig(locale="es", whisper_language="en", kokoro_lang_code="a")
    resolved = apply_resolved_locale(cfg)
    assert resolved.locale == "es"
    assert resolved.whisper_language == "es"
    assert resolved.kokoro_lang_code == "e"


def test_apply_resolved_locale_en_gb_uses_british_kokoro_code() -> None:
    cfg = HecklerConfig(locale="en-gb")
    resolved = apply_resolved_locale(cfg)
    assert resolved.whisper_language == "en"
    assert resolved.kokoro_lang_code == "b"
