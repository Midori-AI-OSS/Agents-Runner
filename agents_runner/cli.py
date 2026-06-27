import os
import sys
import argparse
import traceback


_opencode_cli_overrides: dict[str, str] = {}


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agents_runner",
        description="Agents Runner - Local Containerd GUI",
        epilog="Qt arguments (e.g. --style, --platform) are also accepted and passed through to QApplication.",
    )
    parser.add_argument("--desktop-viewer", action="store_true", help="Run the desktop viewer instead of the main GUI.")
    parser.add_argument("--mcp-server", action="store_true", help="Run the MCP server instead of the main GUI.")
    parser.add_argument("--agent", type=str, default=None, help="Override the opencode agent used by the runtime.")
    parser.add_argument("--model", type=str, default=None, help="Override the opencode model used by the runtime.")
    parser.add_argument("--variant", type=str, default=None, help="Override the opencode variant used by the runtime.")
    return parser


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

        parser = _build_arg_parser()
        parsed, unknown = parser.parse_known_args(sys.argv[1:])
        if parsed.agent is not None:
            _opencode_cli_overrides["agent"] = parsed.agent
        if parsed.model is not None:
            _opencode_cli_overrides["model"] = parsed.model
        if parsed.variant is not None:
            _opencode_cli_overrides["variant"] = parsed.variant

        if parsed.desktop_viewer:
            from agents_runner.ui.desktop_viewer import run_desktop_viewer

            viewer_args = [sys.argv[0]] + unknown
            sys.exit(run_desktop_viewer(viewer_args))

        if parsed.mcp_server:
            import asyncio

            from agents_runner.mcp.cli import run_mcp_server

            try:
                asyncio.run(run_mcp_server())
            except KeyboardInterrupt:
                pass
            return

        from agents_runner.ui.runtime.app import run_app

        run_app([sys.argv[0]] + unknown)
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
