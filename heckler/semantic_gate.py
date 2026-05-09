"""Lexical density gate: filters low-information transcripts before the LLM."""

from __future__ import annotations

import re

from heckler.config import HecklerConfig

# Multi-word filler "you know" is removed with word-boundary regex before tokenization
# so it does not appear as tokens; substring replace would corrupt tokens like "youknown".
_YOU_KNOW_PHRASE = re.compile(r"\byou\s+know\b", re.IGNORECASE)

STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "it",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "of",
        "i",
        "you",
        "we",
        "they",
        "he",
        "she",
        "this",
        "that",
        "was",
        "are",
        "be",
        "have",
        "has",
        "had",
        "do",
        "did",
        "so",
        "just",
        "yeah",
        "okay",
        "uh",
        "um",
        "like",
        "you know",
        "right",
        "well",
        "actually",
        "basically",
        "literally",
    }
)


def _tokenize(text: str) -> list[str]:
    normalized = _YOU_KNOW_PHRASE.sub(" ", text.lower())
    return [t for t in normalized.split() if t]


def compute_density(text: str) -> float:
    """
    Lexical density: ratio of non-stopword tokens to total tokens.
    Returns 0.0 for empty or sub-threshold strings.
    Normalizes to lowercase before stopword check.
    Does not stem or lemmatize — intentional, keeps it O(n) and dependency-free.
    """
    tokens = _tokenize(text)
    if not tokens:
        return 0.0
    non_stop = sum(1 for t in tokens if t not in STOPWORDS)
    return non_stop / len(tokens)


def passes_gate(text: str, config: HecklerConfig) -> tuple[bool, float]:
    """
    Returns (passes, density_score).
    Fails if:
    - word count < config.min_word_count
    - density < config.density_threshold
    Both checks always run; density is always computed and returned for logging.
    """
    tokens = _tokenize(text)
    density = compute_density(text)

    word_ok = len(tokens) >= config.min_word_count
    density_ok = density >= config.density_threshold
    return (word_ok and density_ok, density)
