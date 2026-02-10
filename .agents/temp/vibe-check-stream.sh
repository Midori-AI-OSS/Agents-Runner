#!/usr/bin/env bash
set -u

DEFAULT_URL="https://radio.midori-ai.xyz/radio/v1/stream?q=medium"
STREAM_URL="${1:-$DEFAULT_URL}"
DURATION_SEC="${DURATION_SEC:-1500}"

# Optional playback tuning env overrides.
SAMPLE_RATE="${SAMPLE_RATE:-44100}"
CHANNELS="${CHANNELS:-2}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found in PATH" >&2
  exit 2
fi

if ! command -v aplay >/dev/null 2>&1; then
  echo "aplay not found in PATH" >&2
  exit 2
fi

stamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

run_id="$(date +%F-%H%M%S)"
MAIN_LOG="/tmp/agents-runner-stream-vibe-${run_id}.log"
SUMMARY_LOG="/tmp/agents-runner-stream-vibe-summary-${run_id}.txt"

start_human="$(stamp)"
start_ts="$(date +%s)"

{
  echo "=== Stream Vibe Check (Playback) Start ==="
  echo "Start: ${start_human}"
  echo "URL: ${STREAM_URL}"
  echo "Duration (sec): ${DURATION_SEC}"
  echo "Sample rate: ${SAMPLE_RATE}"
  echo "Channels: ${CHANNELS}"
  echo
  echo "Running: ffmpeg -> aplay"
  echo "Command uses ffmpeg reconnect flags and logs stderr here."
} > "$MAIN_LOG"

echo "Running playback vibe check for ${DURATION_SEC}s"
echo "URL: ${STREAM_URL}"
echo "Log: ${MAIN_LOG}"

run_rc=0
restart_count=0
early_exit_count=0

while true; do
  now_ts="$(date +%s)"
  elapsed_sec=$((now_ts - start_ts))
  if (( elapsed_sec >= DURATION_SEC )); then
    break
  fi

  remaining_sec=$((DURATION_SEC - elapsed_sec))
  restart_count=$((restart_count + 1))
  echo "$(stamp) stream_session_start index=${restart_count} remaining_sec=${remaining_sec}" >> "$MAIN_LOG"

  timeout --signal=INT "${remaining_sec}s" bash -lc '
    set -o pipefail
    ffmpeg -hide_banner -nostdin -loglevel error \
      -reconnect 1 \
      -reconnect_streamed 1 \
      -reconnect_on_network_error 1 \
      -reconnect_on_http_error 4xx,5xx \
      -i "$0" \
      -f s16le -acodec pcm_s16le -ac "$1" -ar "$2" - \
      2>>"$3" | aplay -q -f S16_LE -c "$1" -r "$2" - 2>>"$3"
  ' "$STREAM_URL" "$CHANNELS" "$SAMPLE_RATE" "$MAIN_LOG"
  session_rc=$?

  if [[ "$session_rc" == "124" ]]; then
    run_rc=124
    echo "$(stamp) stream_session_timeout_complete index=${restart_count}" >> "$MAIN_LOG"
    break
  fi

  if [[ "$session_rc" == "0" ]]; then
    early_exit_count=$((early_exit_count + 1))
    echo "$(stamp) stream_session_eof_restart index=${restart_count} early_exits=${early_exit_count}" >> "$MAIN_LOG"
    sleep 1
    continue
  fi

  run_rc="$session_rc"
  echo "$(stamp) stream_session_error index=${restart_count} rc=${session_rc}" >> "$MAIN_LOG"
  break
done

end_human="$(stamp)"
end_ts="$(date +%s)"
run_elapsed=$((end_ts - start_ts))

# timeout exits 124 when duration elapsed naturally.
if [[ "$run_rc" == "124" ]]; then
  status="ok_duration_elapsed"
  final_rc=0
else
  status="pipeline_exit_${run_rc}"
  final_rc="$run_rc"
fi

error_lines=$(grep -Eic 'error|failed|invalid|timed out|connection|broken pipe' "$MAIN_LOG" || true)

{
  echo "=== Stream Vibe Check (Playback) Summary ==="
  echo "Start: ${start_human}"
  echo "End: ${end_human}"
  echo "Run elapsed (sec): ${run_elapsed}"
  echo "URL: ${STREAM_URL}"
  echo "Status: ${status}"
  echo "Session restarts: ${restart_count}"
  echo "Early EOF restarts: ${early_exit_count}"
  echo "Detected error-like log lines: ${error_lines}"
  echo "Main log: ${MAIN_LOG}"
  echo "Summary log: ${SUMMARY_LOG}"
} | tee "$SUMMARY_LOG"

if [[ "$final_rc" -ne 0 ]]; then
  echo "Playback vibe check failed. See ${MAIN_LOG}" >&2
  exit "$final_rc"
fi

exit 0
