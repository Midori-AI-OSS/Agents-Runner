#!/bin/bash
# Common log formatting functions for preflight scripts
# Source this file at the beginning of preflight scripts

# format_log_line - Central log line formatter for shell scripts
# Usage: format_log_line SCOPE SUBSCOPE LEVEL MESSAGE
# Example: format_log_line desktop vnc INFO "Starting Xvnc"
format_log_line() {
    local scope="$1"
    local subscope="$2"
    local level="${3:-INFO}"
    shift 3
    local message="$*"
    
    # Normalize level to uppercase
    level=$(echo "$level" | tr '[:lower:]' '[:upper:]')
    
    # Validate level
    case "$level" in
        DEBUG|INFO|WARN|ERROR)
            ;;
        *)
            level="INFO"
            ;;
    esac
    
    # Output in canonical format: [scope/subscope][LEVEL] message
    echo "[${scope}/${subscope}][${level}] ${message}"
}

# Convenience wrappers for common log levels
log_debug() {
    format_log_line "$1" "$2" DEBUG "${@:3}"
}

log_info() {
    format_log_line "$1" "$2" INFO "${@:3}"
}

log_warn() {
    format_log_line "$1" "$2" WARN "${@:3}"
}

log_error() {
    format_log_line "$1" "$2" ERROR "${@:3}"
}
