import pytest

from heckler.config import HecklerConfig
from heckler.semantic_gate import STOPWORDS, compute_density, passes_gate


@pytest.mark.parametrize(
    ("text", "min_word_count", "density_threshold", "expect_pass", "expect_density"),
    [
        ("", 4, 0.4, False, 0.0),
        ("hello", 4, 0.4, False, 1.0),
        ("the a an is", 4, 0.4, False, 0.0),
        ("like uh um basically literally", 4, 0.4, False, 0.0),
        ("alpha beta gamma delta", 4, 0.4, True, 1.0),
        ("one two three", 4, 0.4, False, 1.0),
        ("one two three four", 4, 0.4, True, 1.0),
        ("one two three four", 5, 0.4, False, 1.0),
        ("x y the a is", 4, 0.4, True, 2 / 5),
        ("x the a is", 4, 0.4, False, 1 / 4),
        ("x y the a", 4, 0.5, True, 2 / 4),
        ("x the a is", 4, 0.5, False, 1 / 4),
    ],
)
def test_passes_gate_table(
    text: str,
    min_word_count: int,
    density_threshold: float,
    expect_pass: bool,
    expect_density: float,
) -> None:
    cfg = HecklerConfig(
        min_word_count=min_word_count,
        density_threshold=density_threshold,
    )
    passes, density = passes_gate(text, cfg)
    assert passes is expect_pass
    assert density == pytest.approx(expect_density)


def test_compute_density_matches_passes_gate_density() -> None:
    """Guards drift: logging uses the same density as the gate decision."""
    cfg = HecklerConfig()
    samples = [
        "",
        "a",
        "the and or",
        "alpha beta gamma delta epsilon",
        "YOU   KNOW    the story",
    ]
    for text in samples:
        _, d_gate = passes_gate(text, cfg)
        assert d_gate == pytest.approx(compute_density(text))


def test_you_know_phrase_removed_not_substring_of_youknown() -> None:
    assert compute_density("youknown") == 1.0
    assert compute_density("you know") == 0.0


def test_stopwords_include_seed_fillers() -> None:
    for w in (
        "like",
        "you know",
        "right",
        "well",
        "actually",
        "basically",
        "literally",
    ):
        assert w in STOPWORDS
