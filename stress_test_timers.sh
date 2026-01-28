#!/bin/bash
# Extended stress test for Qt timer warnings
# Tests with actual task execution scenarios

set -e

WORKSPACE="/home/midori-ai/workspace"
ARTIFACTS="/tmp/agents-artifacts"
LOG_FILE="$ARTIFACTS/stress-test-$(date +%s).log"

echo "=" | tr '=' '\n' | head -80 | tr '\n' '=' ; echo
echo "Extended Stress Test for Qt Timer Warnings"
echo "Task 141-06 - Testing real task execution scenarios"
echo "=" | tr '=' '\n' | head -80 | tr '\n' '=' ; echo
echo

mkdir -p "$ARTIFACTS"

# Function to check for timer warnings
check_warnings() {
    local file="$1"
    local count=$(grep -c "QObject::.*Timer" "$file" 2>/dev/null || echo "0")
    echo "Timer warnings in $file: $count"
    if [ "$count" -gt 0 ]; then
        echo "WARNING: Found timer warnings!"
        grep "QObject::.*Timer" "$file" || true
        return 1
    fi
    return 0
}

echo "[Test 1] Rapid app start/stop cycles"
echo "Testing 5 quick app launches..."
for i in {1..5}; do
    echo "  Cycle $i/5..."
    timeout 2 uv run python main.py > /dev/null 2>> "$LOG_FILE" || true
    sleep 0.5
done
echo "  ✓ Completed 5 cycles"
echo

echo "[Test 2] Slightly longer run to allow initialization"
echo "Running app for 10 seconds..."
timeout 10 uv run python main.py > /dev/null 2>> "$LOG_FILE" || true
echo "  ✓ Completed 10-second run"
echo

echo "[Test 3] Check all captured output for warnings"
if check_warnings "$LOG_FILE"; then
    echo "  ✅ No timer warnings detected in stress test"
    STRESS_TEST_PASSED=1
else
    echo "  ❌ Timer warnings found!"
    STRESS_TEST_PASSED=0
fi
echo

echo "=" | tr '=' '\n' | head -80 | tr '\n' '=' ; echo
echo "Stress Test Summary"
echo "=" | tr '=' '\n' | head -80 | tr '\n' '=' ; echo
echo "Log file: $LOG_FILE"
echo "Log size: $(wc -l < "$LOG_FILE") lines"
echo

if [ "$STRESS_TEST_PASSED" -eq 1 ]; then
    echo "✅ STRESS TEST PASSED"
    echo "No timer warnings detected across multiple app launches and shutdowns."
    exit 0
else
    echo "❌ STRESS TEST FAILED"
    echo "Timer warnings were detected. See log above."
    exit 1
fi
