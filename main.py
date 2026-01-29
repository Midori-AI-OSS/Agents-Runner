import sys

from agents_runner.app import run_app


def main() -> None:
    try:
        # Check if running in desktop viewer mode
        if len(sys.argv) > 1 and sys.argv[1] == "--desktop-viewer":
            # Route to desktop viewer instead of main UI
            from agents_runner.desktop_viewer import run_desktop_viewer
            # Remove --desktop-viewer from argv so argparse works correctly
            viewer_args = [sys.argv[0]] + sys.argv[2:]
            sys.exit(run_desktop_viewer(viewer_args))
        
        run_app(sys.argv)
    except Exception as error:
        print(str(error))


if __name__ == "__main__":
    main()
