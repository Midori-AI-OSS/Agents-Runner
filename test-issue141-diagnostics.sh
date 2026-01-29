#!/usr/bin/env bash
# Test script for Issue #141 QTimer diagnostic logging
# 
# This script runs the Agents Runner with Qt diagnostics enabled to capture
# QTimer cross-thread warnings with full stack traces.

set -e

echo "=========================================="
echo "Issue #141 Qt Diagnostics Test"
echo "=========================================="
echo ""
echo "This script will run Agents Runner with diagnostic logging enabled."
echo "All Qt warnings (especially QTimer warnings) will be captured with"
echo "full stack traces to help identify the source of threading issues."
echo ""

# Set diagnostic environment variable
export AGENTS_RUNNER_QT_DIAGNOSTICS=1

# Show log location
LOG_DIR="$HOME/.midoriai/agents-runner"
LOG_FILE="$LOG_DIR/qt-diagnostics.log"

echo "Diagnostics log will be written to:"
echo "  $LOG_FILE"
echo ""

# Clear existing log if present
if [ -f "$LOG_FILE" ]; then
    echo "Clearing previous diagnostic log..."
    rm "$LOG_FILE"
fi

echo "Starting Agents Runner with diagnostics enabled..."
echo "Please perform the following actions to trigger potential warnings:"
echo "  1. Navigate to different tabs (especially Artifacts tab)"
echo "  2. Select different tasks"
echo "  3. Monitor task status changes"
echo "  4. Watch for any QTimer warnings in the console"
echo ""
echo "Press Ctrl+C to stop the app when done testing."
echo ""
echo "=========================================="
echo ""

# Run the app
uv run main.py

echo ""
echo "=========================================="
echo "Test complete!"
echo ""
echo "Check the diagnostics log at:"
echo "  $LOG_FILE"
echo ""
echo "If QTimer warnings occurred, the log will contain:"
echo "  - Full warning messages"
echo "  - File and line information from Qt"
echo "  - Complete Python stack traces"
echo ""
echo "Share this log file with the development team to help"
echo "identify and fix the source of the warnings."
echo "=========================================="
