#!/usr/bin/env python3
"""
T007 Test Script: Reproduce and analyze duplicate logs with debug output
This script provides instructions and simulates running the test.
Since bash is not available, this provides manual test instructions.
"""
import os
import sys
from pathlib import Path

def setup_artifacts_dir():
    """Create artifacts directory if needed"""
    artifacts_dir = Path("/tmp/agents-artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir

def create_test_instructions():
    """Generate test instructions for T007"""
    output_file = "/tmp/duplicate-logs-debug.txt"
    
    instructions = f"""
{'=' * 80}
T007: Testing for Duplicate Logs with Debug Output
{'=' * 80}

SETUP COMPLETE:
✓ Debug logging enabled in main.py
✓ Debug statements added in T006:
  - _on_bridge_log() - logs [BRIDGE LOG]
  - _on_host_log() - logs [HOST LOG]  
  - _on_task_log() - logs [TASK LOG]
  - _ensure_recovery_log_tail() - logs [RECOVERY SKIP] or [RECOVERY START]

MANUAL TEST INSTRUCTIONS:
{'-' * 80}

1. Run the app manually:
   $ cd /home/midori-ai/workspace
   $ uv run main.py 2>&1 | tee {output_file}

2. Create a simple task that produces logs:
   - Click "New Task" or similar
   - Enter a simple command like: "List files in /tmp"
   - Run the task

3. Watch the console output for debug patterns:
   - [BRIDGE LOG] task=<id> bridge_active=True/False
   - [HOST LOG] task=<id> bridge_active=True/False
   - [TASK LOG] task=<id> line_len=X first_50=...
   - [RECOVERY SKIP] task=<id> reason=bridge_active
   - [RECOVERY START] task=<id> container=<id>

4. Look for duplicate log patterns:
   Pattern A: Same log line appears twice with same content
   Pattern B: [RECOVERY START] even when bridge_active=True
   Pattern C: Multiple [TASK LOG] for same content
   Pattern D: Bridge disconnects then recovery overlaps

5. Document observations below in FINDINGS section

ANALYSIS CHECKLIST:
{'-' * 80}
□ Are logs duplicated in the UI?
□ Do duplicate logs have same [TASK LOG] debug output?
□ Is bridge_active=True when [HOST LOG] fires?
□ Does [RECOVERY START] fire when bridge is active?
□ Is there timing gap between bridge disconnect and recovery?

EXPECTED DEBUG OUTPUT EXAMPLE:
{'-' * 80}
2024-01-15 10:30:15,123 [DEBUG] agents_runner.ui.main_window_task_events: [BRIDGE LOG] task=abc12345 bridge_active=True
2024-01-15 10:30:15,124 [DEBUG] agents_runner.ui.main_window_task_events: [TASK LOG] task=abc12345 line_len=42 first_50=This is a sample log line from the task
2024-01-15 10:30:16,123 [DEBUG] agents_runner.ui.main_window_task_recovery: [RECOVERY SKIP] task=abc12345 reason=bridge_active

OR (if bug exists):

2024-01-15 10:30:15,123 [DEBUG] agents_runner.ui.main_window_task_events: [BRIDGE LOG] task=abc12345 bridge_active=True
2024-01-15 10:30:15,124 [DEBUG] agents_runner.ui.main_window_task_events: [TASK LOG] task=abc12345 line_len=42 first_50=This is a sample log line from the task
2024-01-15 10:30:15,890 [DEBUG] agents_runner.ui.main_window_task_recovery: [RECOVERY START] task=abc12345 container=def67890
2024-01-15 10:30:15,891 [DEBUG] agents_runner.ui.main_window_task_events: [HOST LOG] task=abc12345 bridge_active=False
2024-01-15 10:30:15,892 [DEBUG] agents_runner.ui.main_window_task_events: [TASK LOG] task=abc12345 line_len=42 first_50=This is a sample log line from the task

{'=' * 80}
"""
    
    print(instructions)
    
    # Save instructions to file
    with open(output_file, 'w') as f:
        f.write(instructions)
    
    print(f"\n✓ Instructions saved to: {output_file}")
    print("\nRun the manual test now and document findings in T007.\n")

def main():
    """Main entry point"""
    setup_artifacts_dir()
    create_test_instructions()
    
    print("\nNOTE: Since bash is not available, you need to run the app manually.")
    print("Follow the instructions above to complete T007 testing.\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
