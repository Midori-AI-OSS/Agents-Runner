#!/usr/bin/env bash
set -u

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <stream_url>"
  exit 2
fi

STREAM_URL="$1"
DURATION_SEC="${DURATION_SEC:-1500}"
INTERVAL_SEC="${INTERVAL_SEC:-2}"
CONNECT_TIMEOUT_SEC="${CONNECT_TIMEOUT_SEC:-5}"
MAX_TIME_SEC="${MAX_TIME_SEC:-10}"

MAIN_LOG="/tmp/agents-runner-stream-vibe.log"
EVENT_LOG="/tmp/agents-runner-stream-vibe-events.log"
SUMMARY_LOG="/tmp/agents-runner-stream-vibe-summary.txt"

start_ts="$(date +%s)"
end_ts="$((start_ts + DURATION_SEC))"

checks=0
successes=0
failures=0
timeout_failures=0
connect_failures=0
http_failures=0
other_failures=0

outage_count=0
current_outage_start=0
total_outage_sec=0
longest_outage_sec=0
first_failure_elapsed=""
last_state="unknown"

stamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log_line() {
  local line="$1"
  echo "$line" >> "$MAIN_LOG"
}

log_event() {
  local line="$1"
  echo "$line" >> "$EVENT_LOG"
  echo "$line" >> "$MAIN_LOG"
}

classify_curl_code() {
  local code="$1"
  case "$code" in
    0) echo "ok" ;;
    7) echo "connect" ;;
    28) echo "timeout" ;;
    *) echo "other" ;;
  esac
}

start_human="$(stamp)"
{
  echo "=== Stream Vibe Check Start ==="
  echo "Start: ${start_human}"
  echo "URL: ${STREAM_URL}"
  echo "Duration (sec): ${DURATION_SEC}"
  echo "Interval (sec): ${INTERVAL_SEC}"
  echo "connect-timeout=${CONNECT_TIMEOUT_SEC}s max-time=${MAX_TIME_SEC}s"
} > "$MAIN_LOG"

{
  echo "=== Stream Vibe Check Events ==="
  echo "Start: ${start_human}"
  echo "URL: ${STREAM_URL}"
} > "$EVENT_LOG"

while true; do
  now_ts="$(date +%s)"
  if (( now_ts >= end_ts )); then
    break
  fi

  checks=$((checks + 1))
  elapsed=$((now_ts - start_ts))

  probe_out="$((curl -sS -o /dev/null -L \
    --range 0-65535 \
    --connect-timeout "$CONNECT_TIMEOUT_SEC" \
    --max-time "$MAX_TIME_SEC" \
    -w '%{http_code}::%{size_download}' \
    "$STREAM_URL"; echo "::$?") 2>/dev/null)"

  status_and_size="${probe_out%::*}"
  curl_exit="${probe_out##*::}"
  status_part="${status_and_size%%::*}"
  size_part="${status_and_size##*::}"

  if [[ "$curl_exit" == "0" ]]; then
    if [[ "$status_part" =~ ^2[0-9][0-9]$ ]]; then
      result="ok"
      successes=$((successes + 1))
    else
      result="http"
      failures=$((failures + 1))
      http_failures=$((http_failures + 1))
    fi
  elif [[ "$curl_exit" == "28" && "${size_part%.*}" -gt 0 ]]; then
    result="ok"
    successes=$((successes + 1))
  else
    result="$(classify_curl_code "$curl_exit")"
    failures=$((failures + 1))
    if [[ "$result" == "timeout" ]]; then
      timeout_failures=$((timeout_failures + 1))
    elif [[ "$result" == "connect" ]]; then
      connect_failures=$((connect_failures + 1))
    else
      other_failures=$((other_failures + 1))
    fi
  fi

  timestamp="$(stamp)"
  log_line "${timestamp} elapsed=${elapsed}s check=${checks} result=${result} http=${status_part} curl_exit=${curl_exit}"

  if [[ "$result" == "ok" ]]; then
    if [[ "$last_state" != "ok" ]]; then
      if (( current_outage_start > 0 )); then
        outage_dur=$((now_ts - current_outage_start))
        total_outage_sec=$((total_outage_sec + outage_dur))
        if (( outage_dur > longest_outage_sec )); then
          longest_outage_sec=$outage_dur
        fi
        log_event "${timestamp} RECOVERY elapsed=${elapsed}s outage_duration=${outage_dur}s"
        current_outage_start=0
      else
        log_event "${timestamp} HEALTHY elapsed=${elapsed}s"
      fi
    fi
    last_state="ok"
  else
    if [[ -z "$first_failure_elapsed" ]]; then
      first_failure_elapsed="$elapsed"
    fi
    if [[ "$last_state" == "ok" || "$last_state" == "unknown" ]]; then
      outage_count=$((outage_count + 1))
      current_outage_start=$now_ts
      log_event "${timestamp} GAP_START elapsed=${elapsed}s type=${result} http=${status_part} curl_exit=${curl_exit}"
    fi
    last_state="fail"
  fi

  sleep "$INTERVAL_SEC"
done

finish_ts="$(date +%s)"
finish_human="$(stamp)"
run_elapsed=$((finish_ts - start_ts))

if (( current_outage_start > 0 )); then
  outage_dur=$((finish_ts - current_outage_start))
  total_outage_sec=$((total_outage_sec + outage_dur))
  if (( outage_dur > longest_outage_sec )); then
    longest_outage_sec=$outage_dur
  fi
  log_event "${finish_human} OUTAGE_OPEN_AT_END duration_so_far=${outage_dur}s"
fi

{
  echo "=== Stream Vibe Check Summary ==="
  echo "Start: ${start_human}"
  echo "End: ${finish_human}"
  echo "Run elapsed (sec): ${run_elapsed}"
  echo "URL: ${STREAM_URL}"
  echo "Checks: ${checks}"
  echo "Successes: ${successes}"
  echo "Failures: ${failures}"
  echo "Failure timeout: ${timeout_failures}"
  echo "Failure connect: ${connect_failures}"
  echo "Failure http: ${http_failures}"
  echo "Failure other: ${other_failures}"
  echo "Outage windows: ${outage_count}"
  echo "Total outage seconds: ${total_outage_sec}"
  echo "Longest outage seconds: ${longest_outage_sec}"
  if [[ -n "$first_failure_elapsed" ]]; then
    echo "Time to first failure (sec): ${first_failure_elapsed}"
  else
    echo "Time to first failure (sec): none"
  fi
  echo "Main log: ${MAIN_LOG}"
  echo "Event log: ${EVENT_LOG}"
  echo "Summary log: ${SUMMARY_LOG}"
} | tee "$SUMMARY_LOG"

if (( failures > 0 )); then
  exit 1
fi

exit 0
