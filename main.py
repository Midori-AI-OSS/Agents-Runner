import os
import sys
import traceback


def _is_truthy_env(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _append_qt_logging_rules(existing: str, extra_rules: list[str]) -> str:
    tokens: list[str] = []
    existing_rules = (existing or "").replace("\n", ";").strip()
    if existing_rules:
        tokens.extend(
            rule.strip() for rule in existing_rules.split(";") if rule.strip()
        )

    existing_keys = {
        str(rule.split("=", 1)[0]).strip().lower() for rule in tokens if "=" in rule
    }
    for rule in extra_rules:
        key = str(rule.split("=", 1)[0]).strip().lower()
        if key and key not in existing_keys:
            tokens.append(rule)
            existing_keys.add(key)
    return ";".join(tokens)


def _configure_qt_logging_env() -> None:
    # Keep full Qt output in explicit diagnostics mode.
    if _is_truthy_env("AGENTS_RUNNER_QT_DIAGNOSTICS"):
        return
    os.environ["QT_LOGGING_RULES"] = _append_qt_logging_rules(
        os.environ.get("QT_LOGGING_RULES", ""),
        [
            "default.warning=false",
            "qt.core.qfuture.continuations.warning=false",
            "qt.multimedia.ffmpeg=false",
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
        traceback.print_exception(
            type(error), error, error.__traceback__, file=sys.stderr
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
