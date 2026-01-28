from __future__ import annotations

from agents_runner.environments.parse import parse_env_vars_text
from agents_runner.environments.parse import parse_mounts_text


def test_parse_env_vars_text_parses_kv_and_reports_errors() -> None:
    parsed, errors = parse_env_vars_text(
        "\n".join(
            [
                "# comment",
                "FOO=bar",
                "BADLINE",
                "=emptykey",
                "SPACED = value",
                "",
            ]
        )
    )

    assert parsed == {"FOO": "bar", "SPACED": " value"}
    assert errors == ["line 3: missing '='", "line 4: empty key"]


def test_parse_mounts_text_filters_empty_and_comments() -> None:
    mounts = parse_mounts_text(
        "\n".join(
            [
                "",
                "# comment",
                "/host:/container",
                "  /a:/b  ",
            ]
        )
    )

    assert mounts == ["/host:/container", "/a:/b"]
