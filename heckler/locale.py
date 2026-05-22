from typing import NamedTuple


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
