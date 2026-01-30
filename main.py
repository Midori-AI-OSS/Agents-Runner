import sys
import traceback


def main() -> None:
    try:
        # Check if running in desktop viewer mode
        if len(sys.argv) > 1 and sys.argv[1] == "--desktop-viewer":
            # Route to desktop viewer instead of main UI
            from agents_runner.desktop_viewer import run_desktop_viewer
            # Remove --desktop-viewer from argv so argparse works correctly
            viewer_args = [sys.argv[0]] + sys.argv[2:]
            sys.exit(run_desktop_viewer(viewer_args))

        from agents_runner.app import run_app
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


if __name__ == "__main__":
    main()
