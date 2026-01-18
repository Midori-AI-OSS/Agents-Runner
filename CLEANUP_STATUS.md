# Cleanup Status

## Environment Issue
Bash process is broken - cannot execute Python scripts or shell commands directly.

## Required Operations

### 1. Create artifacts directory
```bash
mkdir -p /tmp/agents-artifacts
```

### 2. Move Python files to artifacts
```bash
mv /home/midori-ai/workspace/cleanup_t006.py /tmp/agents-artifacts/
mv /home/midori-ai/workspace/test_t007.py /tmp/agents-artifacts/
```

### 3. Delete files from .agents/tasks/wip/
```bash
cd /home/midori-ai/workspace/.agents/tasks/wip
rm -f T001-investigate-log-deduplication-strategy.md
rm -f T002-add-log-deduplication-to-on-task-log.md
rm -f T004-coordinate-bridge-and-recovery-log-readers.md
rm -f T006-add-debug-logging-to-log-sources.md
rm -f T007-reproduce-and-analyze-duplicate-logs.md
rm -f T008-implement-fix-for-duplicate-logs.md
rm -f T009-verify-fix-and-cleanup-debug-code.md
rm -f README-DUPLICATE-LOGS.md
```

### 4. Delete files from .agents/tasks/done/
```bash
cd /home/midori-ai/workspace/.agents/tasks/done
rm -f T001-investigate-duplicate-logs.md
rm -f T006-add-debug-logging-to-log-sources.md
rm -f T007-reproduce-and-analyze-duplicate-logs.md
rm -f T008-implement-fix-for-duplicate-logs.md
rm -f T009-verify-fix-and-cleanup-debug-code.md
```

### 5. Delete files from .agents/tasks/taskmaster/
```bash
cd /home/midori-ai/workspace/.agents/tasks/taskmaster
rm -f T001-investigate-duplicate-logs.md
rm -f T007-reproduce-and-analyze-duplicate-logs.md
rm -f T008-implement-fix-for-duplicate-logs.md
rm -f T009-verify-fix-and-cleanup-debug-code.md
```

### 6. Git operations
```bash
cd /home/midori-ai/workspace
git add -A
git commit -m "Fix duplicate logs in task execution"
```

## Alternative: Use cleanup script
```bash
python3 /tmp/cleanup_script.py
```

## Status
⚠️ Awaiting manual execution or environment fix
