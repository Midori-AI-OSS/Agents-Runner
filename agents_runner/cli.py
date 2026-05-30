import os
import sys
import traceback


_opencode_cli_overrides: dict[str, str] = {}


def _parse_opencode_cli_overrides(argv: list[str]) -> None:
    global _opencode_cli_overrides
    parts = list(argv[1:])
    i = 0
    while i < len(parts):
        arg = parts[i]
        if arg in {"--agent", "--model", "--variant"} and i + 1 < len(parts):
            value = parts[i + 1]
            if not value.startswith("--"):
                _opencode_cli_overrides[arg.lstrip("-")] = value
                i += 1
        i += 1


def get_opencode_cli_overrides() -> dict[str, str]:
    return dict(_opencode_cli_overrides)


def _is_truthy_env(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _upsert_qt_logging_rules(existing: str, required_rules: list[str]) -> str:
    tokens: list[str] = []
    existing_rules = (existing or "").replace("\n", ";").strip()
    if existing_rules:
        tokens.extend(rule.strip() for rule in existing_rules.split(";") if rule.strip())

    # Keep the last seen index for each key so we can replace effective rules.
    key_to_index: dict[str, int] = {}
    for idx, rule in enumerate(tokens):
        if "=" not in rule:
            continue
        key = str(rule.split("=", 1)[0]).strip().lower()
        if key:
            key_to_index[key] = idx

    for rule in required_rules:
        key = str(rule.split("=", 1)[0]).strip().lower()
        if not key:
            continue
        existing_idx = key_to_index.get(key)
        if existing_idx is None:
            key_to_index[key] = len(tokens)
            tokens.append(rule)
            continue
        tokens[existing_idx] = rule
    return ";".join(tokens)


def _configure_qt_logging_env() -> None:
    # Keep full Qt output in explicit diagnostics mode.
    if _is_truthy_env("AGENTS_RUNNER_QT_DIAGNOSTICS"):
        return
    os.environ.pop("QT_FFMPEG_DEBUG", None)
    os.environ["QT_LOGGING_RULES"] = _upsert_qt_logging_rules(
        os.environ.get("QT_LOGGING_RULES", ""),
        [
            "default.warning=false",
            "qt.core.qfuture.continuations.warning=false",
            "qt.multimedia.ffmpeg=false",
            "qt.multimedia.ffmpeg.*=false",
        ],
    )


def main() -> None:
    try:
        _configure_qt_logging_env()

        # Check if running in desktop viewer mode
        if len(sys.argv) > 1 and sys.argv[1] == "--desktop-viewer":
            # Route to desktop viewer instead of main UI
            from agents_runner.ui.desktop_viewer import run_desktop_viewer

            # Remove --desktop-viewer from argv so argparse works correctly
            viewer_args = [sys.argv[0]] + sys.argv[2:]
            sys.exit(run_desktop_viewer(viewer_args))

        from agents_runner.ui.runtime.app import run_app

        _parse_opencode_cli_overrides(sys.argv)
        run_app(sys.argv)
    except SystemExit:
        raise
    except BaseException as error:
        report_path = None
        try:
            from agents_runner.diagnostics.crash_reporting import report_fatal_exception

            report_path = report_fatal_exception(
                error,
                context="main",
                argv=list(sys.argv),
            )
        except Exception:
            # Best-effort: never fail to show *something* useful.
            report_path = None

        if report_path is not None:
            print(
                f"Agents Runner crashed. Crash report: {report_path}",
                file=sys.stderr,
                flush=True,
            )
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        sys.exit(1)
