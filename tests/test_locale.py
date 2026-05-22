import pytest

from heckler.config import HecklerConfig, apply_resolved_locale
from heckler.locale import (
    SUPPORTED_LOCALES,
    LocaleProfile,
    UnsupportedLocaleError,
    normalize_locale,
    resolve_locale,
    speech_stack_signature,
    supported_locale_labels,
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


def test_speech_stack_signature_en() -> None:
    cfg = apply_resolved_locale(HecklerConfig(locale="en"))
    assert speech_stack_signature(cfg) == ("en", "a")


def test_speech_stack_signature_es() -> None:
    cfg = apply_resolved_locale(HecklerConfig(locale="es"))
    assert speech_stack_signature(cfg) == ("es", "e")


def test_speech_stack_signature_en_gb() -> None:
    cfg = apply_resolved_locale(HecklerConfig(locale="en-gb"))
    assert speech_stack_signature(cfg) == ("en", "b")


def test_speech_stack_signature_uses_resolved_fields_not_locale_slug() -> None:
    """Stale whisper/kokoro on cfg must not be re-derived from locale."""
    cfg = HecklerConfig(locale="es", whisper_language="en", kokoro_lang_code="a")
    assert speech_stack_signature(cfg) == ("en", "a")


def test_supported_locale_labels() -> None:
    assert supported_locale_labels() == list(SUPPORTED_LOCALES.keys())
