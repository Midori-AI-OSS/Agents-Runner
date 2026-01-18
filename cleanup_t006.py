#!/usr/bin/env python3
"""
Cleanup script to remove T006 from wip folder after successful move to done.
Run this with: python3 cleanup_t006.py
"""

import os
from pathlib import Path

wip_file = Path("/home/midori-ai/workspace/.agents/tasks/wip/T006-add-debug-logging-to-log-sources.md")
done_file = Path("/home/midori-ai/workspace/.agents/tasks/done/T006-add-debug-logging-to-log-sources.md")

# Verify done file exists before removing wip file
if done_file.exists():
    if wip_file.exists():
        os.remove(wip_file)
        print(f"✓ Removed {wip_file}")
    else:
        print(f"✓ File already removed from wip: {wip_file}")
else:
    print(f"✗ ERROR: Done file doesn't exist yet: {done_file}")
    print("  Not removing wip file to avoid data loss.")
