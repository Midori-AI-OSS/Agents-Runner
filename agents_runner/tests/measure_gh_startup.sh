#!/bin/sh
# Launch the real app while tracing each `gh` process launch without saving its arguments.

set -eu
umask 077

usage() {
    printf 'Usage: uv run sh agents_runner/tests/measure_gh_startup.sh [duration-seconds]\n' >&2
    exit 2
}

if [ "$#" -gt 1 ]; then
    usage
fi
duration=${1:-}
if [ -n "$duration" ]; then
    case "$duration" in
        *[!0-9]*) usage ;;
    esac
    if [ "$duration" -lt 1 ]; then
        usage
    fi
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repo_root" || exit 1

for required_command in uv gh mktemp python3; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$required_command" >&2
        exit 1
    fi
done

# Read config without calling load_environments(), which may canonicalize and rewrite its JSON file.
state_context=$(
    uv run --locked python - <<'PY'
import json
from pathlib import Path

from agents_runner.environments.paths import default_data_dir
from agents_runner.persistence import default_state_path, load_state

state = load_state(default_state_path())
settings = state.get("settings", {})
environment_file = Path(default_data_dir()) / "environments.json"
try:
    payload = json.loads(environment_file.read_text(encoding="utf-8"))
except (OSError, ValueError):
    payload = []
records = payload.get("environments", []) if isinstance(payload, dict) else payload
if not isinstance(records, list):
    records = []
environment_count = sum(isinstance(item, dict) for item in records)
try:
    startup_delay_s = max(0, int(settings.get("github_poll_startup_delay_s", 35)))
except (TypeError, ValueError):
    startup_delay_s = 35
print(environment_count, int(bool(settings.get("github_polling_enabled"))), startup_delay_s)
PY
)
set -- $state_context
configured_environment_count=$1
github_polling_enabled=$2
github_poll_startup_delay_s=$3
if [ -z "$duration" ]; then
    # Leave a little startup margin, then capture a full minute after the configured delay.
    duration=$((github_poll_startup_delay_s + 70))
    if [ "$duration" -lt 120 ]; then
        duration=120
    fi
fi

real_gh=$(command -v gh)
diagnostic_root=${AGENTS_RUNNER_GH_TRACE_DIR:-${TMPDIR:-/tmp}}
if ! mkdir -p "$diagnostic_root"; then
    printf 'Cannot create diagnostic directory: %s\n' "$diagnostic_root" >&2
    exit 1
fi
diagnostic_root=$(CDPATH= cd -- "$diagnostic_root" && pwd) || exit 1
run_dir=$(mktemp -d "$diagnostic_root/agents-runner-gh-startup.XXXXXX") || exit 1
chmod 700 "$run_dir"
wrapper_dir=$run_dir/bin
trace_file=$run_dir/gh-launches.tsv
summary_file=$run_dir/summary.txt
timeout_marker=$run_dir/capture-timed-out
mkdir "$wrapper_dir"

# The wrapper records timestamps and coarse command categories only, then replaces itself with gh.
cat >"$wrapper_dir/gh" <<'WRAPPER'
#!/usr/bin/env python3

import os
import sys
import time

args = sys.argv[1:]
command = args[0] if args else ""
subcommand = args[1] if len(args) > 1 else ""
if command == "api":
    category = "api"
elif command == "auth":
    category = f"auth-{subcommand}" if subcommand in {"status", "token", "login"} else "auth-other"
elif command in {"issue", "pr", "repo", "search", "workflow", "run", "release", "gist"}:
    category = command
else:
    category = "other"

try:
    descriptor = os.open(os.environ["GH_TRACE_FILE"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        line = f"{time.monotonic_ns()}\t{category}\n".encode("ascii")
        offset = 0
        while offset < len(line):
            offset += os.write(descriptor, line[offset:])
    finally:
        os.close(descriptor)
except OSError:
    print("Could not write a GitHub CLI diagnostic event.", file=sys.stderr)

real_gh = os.environ.get("GH_REAL_BIN", "")
if not real_gh:
    raise SystemExit("GH_REAL_BIN is not configured")
os.execv(real_gh, [real_gh, *args])
WRAPPER
chmod 700 "$wrapper_dir/gh"

export GH_REAL_BIN=$real_gh
export GH_TRACE_FILE=$trace_file
export PATH=$wrapper_dir:$PATH
run_started_ns=$(python3 -c 'import time; print(time.monotonic_ns())')

printf 'Starting the real Agents Runner for %s seconds.\n' "$duration"
printf 'Using the existing Agents Runner state and GitHub CLI authentication.\n'
printf 'Persisted environment records: %s; global GitHub polling enabled: %s; startup delay: %s seconds.\n' \
    "$configured_environment_count" "$github_polling_enabled" "$github_poll_startup_delay_s"
if [ "$configured_environment_count" -ne 10 ]; then
    printf 'Note: this run uses the current configuration, which has %s environment records (the regression scenario uses 10).\n' \
        "$configured_environment_count"
fi
printf 'Diagnostic output: %s\n' "$run_dir"
printf 'The app will be interrupted after the capture duration; close its window sooner to stop early.\n\n'

# Start a separate process group so closing the window or reaching the limit stops uv and the app.
set +e
trap ':' INT
python3 - "$duration" "$timeout_marker" <<'RUNNER'
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


def stop_process_group(process: subprocess.Popen[bytes], first_signal: int) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    def group_exists() -> bool:
        try:
            os.killpg(process.pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def wait_for_group_exit(timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while group_exists() and time.monotonic() < deadline:
            process.poll()  # Reap uv if it exits before a descendant in its process group.
            time.sleep(0.1)
        return group_exists()

    try:
        os.killpg(process.pid, first_signal)
    except ProcessLookupError:
        pass
    if wait_for_group_exit(5):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if wait_for_group_exit(2):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    process.wait()


duration_s = int(sys.argv[1])
marker = Path(sys.argv[2])
process = subprocess.Popen(["uv", "run", "--locked", "python", "main.py"], start_new_session=True)
try:
    app_status = process.wait(timeout=duration_s)
except subprocess.TimeoutExpired:
    marker.touch()
    stop_process_group(process, signal.SIGINT)
    raise SystemExit(124)
except KeyboardInterrupt:
    stop_process_group(process, signal.SIGINT)
    raise SystemExit(130)
raise SystemExit(app_status if app_status >= 0 else 128 - app_status)
RUNNER
app_status=$?
trap - INT
set -e
run_finished_ns=$(python3 -c 'import time; print(time.monotonic_ns())')
capture_timed_out=0
if [ -f "$timeout_marker" ]; then
    capture_timed_out=1
fi

python3 - "$trace_file" "$summary_file" "$run_started_ns" "$run_finished_ns" "$duration" \
    "$app_status" "$capture_timed_out" "$configured_environment_count" "$github_polling_enabled" \
    "$github_poll_startup_delay_s" <<'SUMMARY'
from __future__ import annotations

import collections
import sys
from pathlib import Path

trace_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
started_ns, finished_ns = int(sys.argv[3]), int(sys.argv[4])
duration_s, app_status, timed_out = int(sys.argv[5]), int(sys.argv[6]), bool(int(sys.argv[7]))
environment_count, polling_enabled, startup_delay_s = int(sys.argv[8]), bool(int(sys.argv[9])), int(sys.argv[10])
capture_end_ns = min(finished_ns, started_ns + duration_s * 1_000_000_000)
observed_s = max(0.0, (capture_end_ns - started_ns) / 1_000_000_000)
events: list[tuple[int, str]] = []
if trace_path.exists():
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        timestamp, separator, category = line.partition("\t")
        if separator:
            try:
                event_ns = int(timestamp)
            except ValueError:
                continue
            if started_ns <= event_ns <= capture_end_ns:
                events.append((event_ns, category))
counts = collections.Counter(category for _, category in events)


def first_window(seconds: int, category: str | None = None) -> int:
    end_ns = min(started_ns + seconds * 1_000_000_000, capture_end_ns)
    return sum(
        started_ns <= timestamp <= end_ns and (category is None or event_category == category)
        for timestamp, event_category in events
    )


def peak_window(seconds: int, category: str | None = None) -> tuple[int, float, float]:
    timestamps = sorted(
        timestamp for timestamp, event_category in events if category is None or event_category == category
    )
    left = 0
    peak_count = 0
    peak_start_ns = peak_end_ns = started_ns
    window_ns = seconds * 1_000_000_000
    for right, timestamp in enumerate(timestamps):
        while timestamp - timestamps[left] >= window_ns:
            left += 1
        if right - left + 1 > peak_count:
            peak_count = right - left + 1
            peak_start_ns, peak_end_ns = timestamps[left], timestamp
    return peak_count, max(0.0, (peak_start_ns - started_ns) / 1e9), max(0.0, (peak_end_ns - started_ns) / 1e9)


def partial(seconds: int) -> str:
    return "" if observed_s >= seconds else f" (partial capture: {observed_s:.3f} seconds)"


peak_10, peak_10_start, peak_10_end = peak_window(10)
peak_60, peak_60_start, peak_60_end = peak_window(60)
auth_10, auth_10_start, auth_10_end = peak_window(10, "auth-status")
auth_60, auth_60_start, auth_60_end = peak_window(60, "auth-status")
lines = [
    "Agents Runner GitHub CLI startup trace",
    "Measurement: host-side gh CLI process launches; excludes isolated-container gh and HTTP subrequests inside gh.",
    f"Requested capture duration: {duration_s} seconds",
    f"Observed capture duration: {observed_s:.3f} seconds",
    "Summary counts are limited to the requested capture window; shutdown events may appear only in the TSV trace.",
    f"App result: {'capture duration reached' if timed_out else f'exited with status {app_status}'}",
    f"Raw persisted environment records in environments.json: {environment_count} (target is 10; not a validity/eligibility check)",
    f"Global GitHub polling enabled: {'yes' if polling_enabled else 'no'}",
    f"Configured GitHub polling startup delay: {startup_delay_s} seconds",
    f"Total gh launches: {len(events)}",
    f"gh launches in first 10 seconds{partial(10)}: {first_window(10)}",
    f"gh launches in first 60 seconds{partial(60)}: {first_window(60)}",
    f"gh auth status launches total: {counts['auth-status']}",
    f"gh auth status launches in first 10 seconds{partial(10)}: {first_window(10, 'auth-status')}",
    f"gh auth status launches in first 60 seconds{partial(60)}: {first_window(60, 'auth-status')}",
    f"Peak rolling 10-second gh launches{partial(10)}: {peak_10} ({peak_10_start:.3f}s–{peak_10_end:.3f}s)",
    f"Peak rolling 60-second gh launches{partial(60)}: {peak_60} ({peak_60_start:.3f}s–{peak_60_end:.3f}s)",
    f"Peak rolling 10-second gh auth status launches{partial(10)}: {auth_10} ({auth_10_start:.3f}s–{auth_10_end:.3f}s)",
    f"Peak rolling 60-second gh auth status launches{partial(60)}: {auth_60} ({auth_60_start:.3f}s–{auth_60_end:.3f}s)",
    "",
    "Launches by command category:",
]
lines.extend([f"  {category}: {count}" for category, count in sorted(counts.items())] or ["  (none observed)"])
lines.extend(
    [
        "",
    "Trace fields: monotonic timestamp in nanoseconds and command category only. Arguments, repo names, URLs, tokens, and output are not recorded.",
    ]
)
summary = "\n".join(lines) + "\n"
summary_path.write_text(summary, encoding="utf-8")
print(summary, end="")
print(f"Saved summary: {summary_path}")
print(f"Saved event trace: {trace_path}")
SUMMARY

if [ "$capture_timed_out" -eq 1 ]; then
    exit 0
fi
exit "$app_status"
