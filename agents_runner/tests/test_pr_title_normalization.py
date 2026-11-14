import pytest

from agents_runner.pr_metadata import normalize_pr_title


@pytest.mark.parametrize("title", ["", "   ", "\n\t\n"])
def test_blank_title_uses_fallback(title: str) -> None:
    assert normalize_pr_title(title, fallback="Fallback title") == "Fallback title"


def test_multiline_title_uses_first_line() -> None:
    assert normalize_pr_title("  First line\nSecond line  ", fallback="fallback") == "First line"


def test_long_fallback_is_truncated() -> None:
    assert normalize_pr_title(" ", fallback="a" * 80) == "a" * 69 + "..."
