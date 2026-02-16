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


def _parse_headless_mode(argv: list[str]) -> tuple[list[str], bool]:
    """Return cleaned argv and whether headless startup mode is enabled."""
    headless_requested = _is_truthy_env("AGENTS_RUNNER_HEADLESS")
    cleaned = [argv[0]]
    for arg in argv[1:]:
        if arg == "--headless":
            headless_requested = True
            continue
        cleaned.append(arg)
    return cleaned, headless_requested


def _configure_headless_runtime_env() -> None:
    """Apply explicit headless-safe Qt defaults for SSH/X11 and no-display runs."""
    has_display = bool(str(os.environ.get("DISPLAY", "")).strip())
    platform = str(os.environ.get("QT_QPA_PLATFORM", "")).strip().lower()

    if has_display:
        if not platform:
            os.environ["QT_QPA_PLATFORM"] = "xcb"
    else:
        if platform in {"", "xcb"}:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"

    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    os.environ.setdefault("QT_XCB_FORCE_SOFTWARE_OPENGL", "1")
    os.environ.setdefault("QT_OPENGL", "software")


def main() -> None:
    try:
        argv, headless_mode = _parse_headless_mode(list(sys.argv))
        if headless_mode:
            _configure_headless_runtime_env()

        _configure_qt_logging_env()

        # Check if running in desktop viewer mode
        if len(argv) > 1 and argv[1] == "--desktop-viewer":
            # Route to desktop viewer instead of main UI
            from agents_runner.ui.desktop_viewer import run_desktop_viewer

            # Remove --desktop-viewer from argv so argparse works correctly
            viewer_args = [argv[0]] + argv[2:]
            sys.exit(run_desktop_viewer(viewer_args))

        from agents_runner.ui.runtime.app import run_app

        run_app(argv)
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
