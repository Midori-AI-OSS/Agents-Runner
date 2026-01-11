# Task: Add breadcrumb logging system

## Description
Create a lightweight breadcrumb logging system that tracks recent application events for inclusion in crash reports.

## Requirements
1. Create a breadcrumb logger module
2. Track recent events in a circular buffer (e.g., last 50-100 events)
3. Events to track:
   - Task started/completed/failed
   - Container launched
   - Agent selected
   - Retry scheduled
   - Other significant application events
4. Provide API to:
   - Add breadcrumb entry with timestamp and message
   - Retrieve recent breadcrumbs as a list
5. Integrate breadcrumb logger with crash handler
6. Add breadcrumb calls at key points in the application

## Acceptance Criteria
- [ ] Breadcrumb logging system stores recent events
- [ ] Circular buffer prevents unlimited memory growth
- [ ] Each breadcrumb has timestamp and message
- [ ] API provided to add and retrieve breadcrumbs
- [ ] Crash reports include breadcrumb log
- [ ] Key application events are logged as breadcrumbs
- [ ] Code follows type hint standards

## Related Tasks
- Depends on: d0f6e542
- Blocks: None

## Notes
- Use collections.deque for circular buffer
- Keep breadcrumbs in memory only (don't persist to disk except in crash reports)
- Breadcrumb format: `[YYYY-MM-DD HH:MM:SS] Event description`
- Integrate with existing logging if appropriate
- Create module at: `agents_runner/diagnostics/breadcrumbs.py`
- Class/module structure:
  ```python
  from collections import deque
  from datetime import datetime
  
  class BreadcrumbLogger:
      def __init__(self, max_size: int = 100):
          self._crumbs = deque(maxlen=max_size)
      
      def add(self, message: str) -> None:
          # Add timestamped breadcrumb
      
      def get_recent(self) -> list[str]:
          # Return formatted breadcrumbs
  ```
- Create global instance: `_breadcrumb_logger = BreadcrumbLogger()`
- Key integration points to add breadcrumb calls:
  - Task start/complete: `agents_runner/ui/main_window_task_events.py`
  - Container launch: `agents_runner/docker/agent_worker.py`
  - Agent selection: `agents_runner/ui/main_window_tasks_agent.py`
