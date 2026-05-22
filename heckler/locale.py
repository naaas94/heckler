from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from heckler.config import HecklerConfig


class UnsupportedLocaleError(ValueError):
    """Raised when a locale slug is empty or not in SUPPORTED_LOCALES."""


class LocaleProfile(NamedTuple):
    whisper_language: str
    kokoro_lang_code: str


SUPPORTED_LOCALES: dict[str, LocaleProfile] = {
    "en": LocaleProfile(whisper_language="en", kokoro_lang_code="a"),
    "en-us": LocaleProfile(whisper_language="en", kokoro_lang_code="a"),
    "en-gb": LocaleProfile(whisper_language="en", kokoro_lang_code="b"),
    "es": LocaleProfile(whisper_language="es", kokoro_lang_code="e"),
}


def normalize_locale(raw: str) -> str:
    normalized = raw.strip().lower()
    if not normalized:
        raise UnsupportedLocaleError("locale must be non-empty after normalization")
    return normalized


def resolve_locale(locale: str) -> LocaleProfile:
    key = normalize_locale(locale)
    try:
        return SUPPORTED_LOCALES[key]
    except KeyError as exc:
        raise UnsupportedLocaleError(f"unsupported locale: {key!r}") from exc


def speech_stack_signature(cfg: HecklerConfig) -> tuple[str, str]:
    """Return the (whisper_language, kokoro_lang_code) identity tuple for reload comparison.

    cfg must already have resolved locale fields (call apply_resolved_locale first).
    """
    return (cfg.whisper_language, cfg.kokoro_lang_code)


def supported_locale_labels() -> list[str]:
    """Return the ordered list of supported locale slugs for GUI population."""
    return list(SUPPORTED_LOCALES.keys())
