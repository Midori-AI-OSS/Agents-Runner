import os
import sys
import shutil
import subprocess
import shlex

from dataclasses import dataclass


@dataclass(frozen=True)
class TerminalOption:
    terminal_id: str
    label: str
    kind: str
    exe: str | None = None


def detect_terminal_options() -> list[TerminalOption]:
    platform = sys.platform
    options: list[TerminalOption] = []

    if platform == "darwin":
        if shutil.which("osascript") is None:
            return []
        options.append(TerminalOption("mac-terminal", "Terminal.app", "mac-terminal"))
        if _mac_has_app("iTerm.app") or _mac_has_app("iTerm2.app"):
            options.append(TerminalOption("mac-iterm", "iTerm", "mac-iterm"))
        return options

    if platform.startswith("linux"):
        terminal_hint = os.environ.get("TERMINAL") or ""
        hint_exe = ""
        if terminal_hint.strip():
            try:
                hint_exe = shlex.split(terminal_hint.strip())[0]
            except ValueError:
                hint_exe = (
                    terminal_hint.strip().split()[0]
                    if terminal_hint.strip().split()
                    else ""
                )
        if hint_exe:
            hint_base = os.path.basename(hint_exe)
            hint_terminal_id = hint_base or "terminal-env"
            resolved = shutil.which(hint_exe)
            if resolved:
                options.append(
                    TerminalOption(
                        hint_terminal_id,
                        f"{hint_base or hint_exe} ($TERMINAL)",
                        "linux-exe",
                        exe=resolved,
                    )
                )

        candidates: list[tuple[str, str, str]] = [
            ("konsole", "Konsole", "konsole"),
            ("kgx", "GNOME Console", "kgx"),
            ("gnome-console", "GNOME Console", "gnome-console"),
            ("gnome-terminal", "GNOME Terminal", "gnome-terminal"),
            ("x-terminal-emulator", "x-terminal-emulator", "x-terminal-emulator"),
            ("mate-terminal", "MATE Terminal", "mate-terminal"),
            ("tilix", "Tilix", "tilix"),
            ("kitty", "Kitty", "kitty"),
            ("wezterm", "WezTerm", "wezterm"),
            ("alacritty", "Alacritty", "alacritty"),
            ("foot", "foot", "foot"),
            ("footclient", "footclient", "footclient"),
            ("terminator", "Terminator", "terminator"),
            ("lxterminal", "LXTerminal", "lxterminal"),
            ("qterminal", "QTerminal", "qterminal"),
            ("xfce4-terminal", "XFCE Terminal", "xfce4-terminal"),
            ("xterm", "xterm", "xterm"),
        ]
        for terminal_id, label, exe in candidates:
            resolved = shutil.which(exe)
            if resolved:
                if any(opt.terminal_id == terminal_id for opt in options):
                    continue
                options.append(
                    TerminalOption(terminal_id, label, "linux-exe", exe=resolved)
                )
        return options

    return []


def launch_in_terminal(
    option: TerminalOption, bash_script: str, cwd: str | None = None
) -> None:
    cwd = os.path.abspath(os.path.expanduser(cwd)) if cwd else None

    if option.kind == "linux-exe":
        args = linux_terminal_args(
            option.terminal_id, option.exe or option.terminal_id, bash_script, cwd=cwd
        )
        subprocess.Popen(args, start_new_session=True)
        return

    if option.kind == "mac-terminal":
        _mac_run_osascript_terminal(bash_script, cwd=cwd)
        return

    if option.kind == "mac-iterm":
        _mac_run_osascript_iterm(bash_script, cwd=cwd)
        return

    raise RuntimeError(f"Unsupported terminal kind: {option.kind}")


def linux_terminal_args(
    terminal_id: str, exe: str, bash_script: str, cwd: str | None
) -> list[str]:
    command = bash_script
    if cwd:
        command = f"cd {shlex_quote(cwd)}; {bash_script}"

    if terminal_id in {"kgx", "gnome-console"}:
        return [exe, "--", "bash", "-lc", command]

    if terminal_id == "konsole":
        args = [exe]
        if cwd:
            args.extend(["--workdir", cwd])
        args.extend(["-e", "bash", "-lc", command])
        return args

    if terminal_id == "mate-terminal":
        args = [exe]
        if cwd:
            args.extend(["--working-directory", cwd])
        args.extend(["--", "bash", "-lc", command])
        return args

    if terminal_id == "gnome-terminal":
        args = [exe]
        if cwd:
            args.extend(["--working-directory", cwd])
        args.extend(["--", "bash", "-lc", command])
        return args

    if terminal_id == "xfce4-terminal":
        args = [exe]
        if cwd:
            args.extend(["--working-directory", cwd])
        args.extend(["-x", "bash", "-lc", command])
        return args

    if terminal_id == "wezterm":
        args = [exe, "start"]
        if cwd:
            args.extend(["--cwd", cwd])
        args.extend(["--", "bash", "-lc", command])
        return args

    if terminal_id == "kitty":
        args = [exe]
        if cwd:
            args.extend(["--directory", cwd])
        args.extend(["bash", "-lc", command])
        return args

    if terminal_id in {"foot", "footclient"}:
        return [exe, "-e", "bash", "-lc", command]

    if terminal_id in {"tilix", "lxterminal", "qterminal"}:
        return [exe, "-e", "bash", "-lc", command]

    if terminal_id == "alacritty":
        args = [exe]
        if cwd:
            args.extend(["--working-directory", cwd])
        args.extend(["-e", "bash", "-lc", command])
        return args

    if terminal_id in {"x-terminal-emulator", "terminator", "xterm"}:
        # No reliable working-directory flag across these; just cd inside bash.
        if terminal_id == "terminator":
            return [exe, "-x", "bash", "-lc", command]
        return [exe, "-e", "bash", "-lc", command]

    return [exe, "-e", "bash", "-lc", command]


def _mac_run_osascript_terminal(bash_script: str, cwd: str | None) -> None:
    cmd = bash_script
    if cwd:
        cmd = f"cd {shlex_quote(cwd)}; {bash_script}"
    full = _osascript_quote(f"bash -lc {shlex_quote(cmd)}")
    script = "\n".join(
        [
            'tell application "Terminal"',
            f"  do script {full}",
            "  activate",
            "end tell",
        ]
    )
    subprocess.Popen(["osascript", "-e", script], start_new_session=True)


def _mac_run_osascript_iterm(bash_script: str, cwd: str | None) -> None:
    cmd = bash_script
    if cwd:
        cmd = f"cd {shlex_quote(cwd)}; {bash_script}"
    full = _osascript_quote(f"bash -lc {shlex_quote(cmd)}")
    script = "\n".join(
        [
            'tell application "iTerm"',
            "  activate",
            "  if (count of windows) = 0 then",
            "    create window with default profile",
            "  else",
            "    create tab with default profile",
            "  end if",
            "  tell current session of current window",
            f"    write text {full}",
            "  end tell",
            "end tell",
        ]
    )
    subprocess.Popen(["osascript", "-e", script], start_new_session=True)


def _mac_has_app(app_name: str) -> bool:
    for base in ("/Applications", os.path.expanduser("~/Applications")):
        if os.path.isdir(os.path.join(base, app_name)):
            return True
    return False


def _osascript_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def shlex_quote(value: str) -> str:
    if value == "":
        return "''"
    if not any(ch in value for ch in " \t\n'\"\\$`!#&()[]{};<>?|*"):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"
