# Usage/Rate Limit Watch System Design & Implementation Guide

**Audit ID:** 04-usage-watch-design  
**Date:** 2025-01-07  
**Auditor:** Auditor Mode  
**Purpose:** Detailed implementation guidance for Task 3 (Usage/Rate Limit Watch System)  
**Related Documents:**
- `.codex/audit/02-task-breakdown.md` (Overall refactor plan)
- `.codex/audit/03-run-supervisor-design.md` (Run supervisor integration)

---

## Executive Summary

The Usage/Rate Limit Watch System will provide real-time monitoring of agent API usage and quota status, with automatic cooldown management to prevent rate-limit errors. This system MUST distinguish between two distinct concepts:

1. **Usage/Quota Watching** - Proactive monitoring of remaining API quota
2. **Rate-Limit Detection & Cooldown** - Reactive response to rate-limit errors

**Critical Finding:** The requirements describe BOTH concepts but conflate them. This design separates them clearly.

**Key Architecture Decisions:**
- **Generalized data model** - Works for all agents (Codex, Claude, Copilot, Gemini)
- **Plugin architecture** - Per-agent watchers implement common interface
- **Polling-based** - 30-minute intervals when agent selected or task running
- **Cooldown at launch** - Check cooldown when user presses "Run Agent", NOT earlier
- **Task-scoped fallback** - Cooldown bypass/fallback doesn't change environment defaults
- **Graceful degradation** - Missing/broken watchers don't block usage

---

## System Architecture


### 1. Conceptual Separation

```
┌─────────────────────────────────────────────────────────────┐
│                    USAGE WATCH SYSTEM                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────┐    ┌──────────────────────────┐ │
│  │  PROACTIVE WATCHING    │    │  REACTIVE COOLDOWN       │ │
│  │  (Optional Enhancement)│    │  (MUST SHIP)             │ │
│  ├────────────────────────┤    ├──────────────────────────┤ │
│  │ • Poll usage APIs      │    │ • Detect rate-limit      │ │
│  │ • Show quota % in UI   │    │   errors in logs         │ │
│  │ • Warning when low     │    │ • Track cooldown state   │ │
│  │ • Per-agent watchers   │    │ • Modal on launch        │ │
│  │                        │    │ • Fallback/bypass        │ │
│  └────────────────────────┘    └──────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**MUST SHIP (Task 3 Core):**
- Rate-limit error detection (from logs/exit codes)
- Cooldown tracking per agent
- Cooldown modal on "Run Agent" button click
- Bypass and fallback functionality

**MAY SHIP (Task 3 Enhancement):**
- OpenAI Codex usage watcher (GET /wham/usage)
- Claude/Copilot/Gemini usage watchers (if APIs available)
- Usage badge display in UI
- Proactive warnings when quota low

**Priority:** Implement cooldown system first, add watchers incrementally.

---

## Part 1: Common Data Model (MUST SHIP)

### 1.1 Agent Watch State

This data model supports BOTH proactive watching AND reactive cooldown tracking.

```python
# agents_runner/core/agent/watch_state.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SupportLevel(Enum):
    """Level of usage watching support for an agent."""
    FULL = "full"              # API available, watcher implemented
    BEST_EFFORT = "best_effort"  # No API, detect from errors only
    UNKNOWN = "unknown"        # Not yet investigated


class AgentStatus(Enum):
    """Current operational status of an agent."""
    READY = "ready"            # Available for use
    ON_COOLDOWN = "on_cooldown"  # Rate-limited, cooling down
    QUOTA_LOW = "quota_low"    # <10% quota remaining
    QUOTA_EXHAUSTED = "quota_exhausted"  # 0% quota remaining
    UNAVAILABLE = "unavailable"  # Not installed/configured


@dataclass
class UsageWindow:
    """A single usage/quota window (e.g., hourly, daily, weekly)."""
    name: str                  # "5h", "weekly", "daily", etc.
    used: int                  # Requests used
    limit: int                 # Request limit
    remaining: int             # Requests remaining
    remaining_percent: float   # Percentage remaining (0-100)
    reset_at: datetime | None  # When window resets


@dataclass
class AgentWatchState:
    """Complete watch state for a single agent."""
    
    # Identity
    provider_name: str         # "codex", "claude", "copilot", "gemini"
    
    # Support level
    support_level: SupportLevel = SupportLevel.UNKNOWN
    
    # Current status
    status: AgentStatus = AgentStatus.READY
    
    # Usage windows (optional, only if watcher available)
    windows: list[UsageWindow] = field(default_factory=list)
    
    # Cooldown tracking (reactive)
    last_rate_limited_at: datetime | None = None
    cooldown_until: datetime | None = None
    cooldown_reason: str = ""  # Error message that triggered cooldown
    
    # Last check metadata
    last_checked_at: datetime | None = None
    last_error: str = ""       # Last watcher error, if any
    
    # Raw response (for debugging)
    raw_data: dict[str, Any] = field(default_factory=dict)


    def is_on_cooldown(self) -> bool:
        """Check if agent is currently on cooldown."""
        if not self.cooldown_until:
            return False
        return datetime.now(timezone.utc) < self.cooldown_until
    
    
    def cooldown_seconds_remaining(self) -> float:
        """Get seconds remaining in cooldown, or 0 if not on cooldown."""
        if not self.is_on_cooldown():
            return 0.0
        if not self.cooldown_until:
            return 0.0
        delta = self.cooldown_until - datetime.now(timezone.utc)
        return max(0.0, delta.total_seconds())
    
    
    def primary_window_display(self) -> str:
        """Get display string for primary usage window."""
        if not self.windows:
            return "Unknown"
        primary = self.windows[0]
        return f"{primary.name}: {primary.remaining_percent:.0f}% left"
    
    
    def all_windows_display(self) -> str:
        """Get display string for all usage windows."""
        if not self.windows:
            return "Unknown"
        parts = [
            f"{w.name}: {w.remaining_percent:.0f}% left"
            for w in self.windows
        ]
        return " • ".join(parts)
```

### 1.2 Watch State Storage

Store watch state in persistence layer alongside tasks/environments.

```python
# agents_runner/persistence.py (additions)

def load_watch_state(state: dict[str, Any]) -> dict[str, AgentWatchState]:
    """Load agent watch state from persistence.
    
    Returns:
        Dict mapping provider_name -> AgentWatchState
    """
    watch_data = state.get("agent_watch", {})
    if not isinstance(watch_data, dict):
        return {}
    
    result = {}
    for provider_name, data in watch_data.items():
        if not isinstance(data, dict):
            continue
        
        # Deserialize cooldown timestamps
        last_rate_limited_at = None
        if data.get("last_rate_limited_at"):
            last_rate_limited_at = _dt_from_str(data["last_rate_limited_at"])
        
        cooldown_until = None
        if data.get("cooldown_until"):
            cooldown_until = _dt_from_str(data["cooldown_until"])
        
        last_checked_at = None
        if data.get("last_checked_at"):
            last_checked_at = _dt_from_str(data["last_checked_at"])
        
        # Deserialize windows
        windows = []
        for w_data in data.get("windows", []):
            if not isinstance(w_data, dict):
                continue
            reset_at = None
            if w_data.get("reset_at"):
                reset_at = _dt_from_str(w_data["reset_at"])
            windows.append(UsageWindow(
                name=w_data.get("name", ""),
                used=w_data.get("used", 0),
                limit=w_data.get("limit", 0),
                remaining=w_data.get("remaining", 0),
                remaining_percent=w_data.get("remaining_percent", 0.0),
                reset_at=reset_at,
            ))
        
        result[provider_name] = AgentWatchState(
            provider_name=provider_name,
            support_level=SupportLevel(data.get("support_level", "unknown")),
            status=AgentStatus(data.get("status", "ready")),
            windows=windows,
            last_rate_limited_at=last_rate_limited_at,
            cooldown_until=cooldown_until,
            cooldown_reason=data.get("cooldown_reason", ""),
            last_checked_at=last_checked_at,
            last_error=data.get("last_error", ""),
            raw_data=data.get("raw_data", {}),
        )
    
    return result


def save_watch_state(state: dict[str, Any], watch_states: dict[str, AgentWatchState]) -> None:
    """Save agent watch state to persistence."""
    watch_data = {}
    
    for provider_name, ws in watch_states.items():
        watch_data[provider_name] = {
            "provider_name": ws.provider_name,
            "support_level": ws.support_level.value,
            "status": ws.status.value,
            "windows": [
                {
                    "name": w.name,
                    "used": w.used,
                    "limit": w.limit,
                    "remaining": w.remaining,
                    "remaining_percent": w.remaining_percent,
                    "reset_at": _dt_to_str(w.reset_at),
                }
                for w in ws.windows
            ],
            "last_rate_limited_at": _dt_to_str(ws.last_rate_limited_at),
            "cooldown_until": _dt_to_str(ws.cooldown_until),
            "cooldown_reason": ws.cooldown_reason,
            "last_checked_at": _dt_to_str(ws.last_checked_at),
            "last_error": ws.last_error,
            "raw_data": ws.raw_data,
        }
    
    state["agent_watch"] = watch_data
```

---

## Part 2: Rate-Limit Detection & Cooldown (MUST SHIP)

### 2.1 Rate-Limit Detection

This functionality is **ALREADY PARTIALLY IMPLEMENTED** in `execution/supervisor.py`.

**Current Implementation:**
- `classify_error()` function (lines 54-134)
- Returns `ErrorType.RATE_LIMIT` when rate-limit patterns detected
- Patterns: "rate.?limit", "429", "too.?many.?requests", "quota.?exceeded"

**Enhancements Needed:**

```python
# agents_runner/core/agent/rate_limit.py

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any


class RateLimitDetector:
    """Detects rate-limit errors from agent logs and exit codes."""
    
    # Per-agent rate-limit patterns
    PATTERNS = {
        "codex": [
            (r"rate.?limit.*exceeded", 60),
            (r"429.*too.?many.?requests", 60),
            (r"quota.*exceeded", 3600),  # Longer cooldown for quota
            (r"retry.*after.*(\d+)", None),  # Extract duration
        ],
        "claude": [
            (r"rate_limit_error", 60),
            (r"too_many_requests", 60),
            (r"429", 60),
        ],
        "copilot": [
            (r"rate limit.*exceeded", 60),
            (r"wait.*(\d+).*seconds?", None),  # Extract duration
        ],
        "gemini": [
            (r"quota exceeded", 60),
            (r"rate limit", 60),
            (r"429", 60),
            (r"resource_exhausted", 60),
        ],
    }
    
    
    @staticmethod
    def detect(
        agent_cli: str,
        exit_code: int,
        logs: list[str],
        container_state: dict[str, Any] | None = None,
    ) -> tuple[bool, int]:
        """Detect rate-limit error and extract cooldown duration.
        
        Args:
            agent_cli: Agent CLI name ("codex", "claude", etc.)
            exit_code: Container exit code
            logs: Container log lines
            container_state: Optional container state dict
        
        Returns:
            (is_rate_limited, cooldown_seconds)
            If not rate-limited, returns (False, 0)
            If rate-limited, returns (True, duration_in_seconds)
        """
        # Check exit code (429 = Too Many Requests in HTTP)
        if exit_code == 429:
            return True, 60
        
        # Get patterns for this agent
        patterns = RateLimitDetector.PATTERNS.get(agent_cli, [])
        
        # Scan recent logs (last 100 lines)
        for line in logs[-100:]:
            line_lower = line.lower()
            
            for pattern, default_cooldown in patterns:
                match = re.search(pattern, line_lower)
                if not match:
                    continue
                
                # Found rate-limit indicator
                if default_cooldown is None:
                    # Pattern includes duration extraction
                    try:
                        duration = int(match.group(1))
                        return True, duration
                    except (IndexError, ValueError):
                        return True, 60  # Fallback
                else:
                    return True, default_cooldown
        
        return False, 0
    
    
    @staticmethod
    def record_rate_limit(
        watch_state: AgentWatchState,
        cooldown_seconds: int,
        reason: str = "",
    ) -> None:
        """Record rate-limit event in watch state.
        
        Args:
            watch_state: Agent watch state to update
            cooldown_seconds: Cooldown duration in seconds
            reason: Human-readable reason (log excerpt)
        """
        now = datetime.now(timezone.utc)
        watch_state.last_rate_limited_at = now
        watch_state.cooldown_until = now + timedelta(seconds=cooldown_seconds)
        watch_state.cooldown_reason = reason
        watch_state.status = AgentStatus.ON_COOLDOWN
    
    
    @staticmethod
    def clear_cooldown(watch_state: AgentWatchState) -> None:
        """Clear cooldown state (user bypass)."""
        watch_state.cooldown_until = None
        watch_state.status = AgentStatus.READY
```

### 2.2 Integration with Supervisor

**File:** `agents_runner/execution/supervisor.py`

**Modifications:**

```python
# Add to TaskSupervisor.__init__():
self._watch_states: dict[str, AgentWatchState] = {}  # Passed from UI

# Add to TaskSupervisor.run(), after error classification:

if error_type == ErrorType.RATE_LIMIT:
    # Record cooldown
    is_rate_limited, cooldown_seconds = RateLimitDetector.detect(
        agent.agent_cli,
        result.exit_code,
        self._last_logs,
        self._last_container_state,
    )
    
    if is_rate_limited:
        # Get or create watch state
        watch_state = self._watch_states.get(agent.agent_cli)
        if not watch_state:
            watch_state = AgentWatchState(provider_name=agent.agent_cli)
            self._watch_states[agent.agent_cli] = watch_state
        
        # Record rate-limit event
        reason = self._last_logs[-10:] if self._last_logs else ""
        RateLimitDetector.record_rate_limit(
            watch_state,
            cooldown_seconds,
            reason="\n".join(reason),
        )
        
        self._on_log(
            f"[supervisor] rate-limit detected, cooldown for {cooldown_seconds}s"
        )
```

---

## Part 3: Cooldown Modal UI (MUST SHIP)

### 3.1 Modal Design

**File:** `agents_runner/ui/dialogs/cooldown_modal.py` (NEW)

**Visual Design:**

```
┌─────────────────────────────────────────────────────────┐
│  Agent On Cooldown                                   [X] │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ⚠  OpenAI Codex is currently rate-limited             │
│                                                          │
│  Cooldown Time Remaining: 42 seconds                    │
│                                                          │
│  Reason: rate limit exceeded (quota: 0%)                │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Options:                                            │ │
│  │                                                     │ │
│  │ • Use Fallback Agent (Claude Code)                 │ │
│  │   Run this task with the next agent in your        │ │
│  │   fallback chain. This won't change your default.  │ │
│  │                                                     │ │
│  │ • Bypass Cooldown                                  │ │
│  │   Attempt to run anyway. The agent may still       │ │
│  │   fail if rate-limited.                            │ │
│  │                                                     │ │
│  │ • Cancel                                            │ │
│  │   Don't start this task now.                       │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│           [Use Fallback]  [Bypass]  [Cancel]            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
# agents_runner/ui/dialogs/cooldown_modal.py

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from agents_runner.core.agent.watch_state import AgentWatchState
from agents_runner.widgets import GlassCard


class CooldownAction:
    """User's choice in cooldown modal."""
    USE_FALLBACK = "use_fallback"
    BYPASS = "bypass"
    CANCEL = "cancel"


class CooldownModal(QDialog):
    """Modal dialog shown when agent is on cooldown."""
    
    def __init__(
        self,
        parent: QWidget | None,
        agent_name: str,
        watch_state: AgentWatchState,
        fallback_agent_name: str | None = None,
    ) -> None:
        """Initialize cooldown modal.
        
        Args:
            parent: Parent widget
            agent_name: Display name of agent on cooldown
            watch_state: Agent watch state
            fallback_agent_name: Name of fallback agent, or None if no fallback
        """
        super().__init__(parent)
        
        self._watch_state = watch_state
        self._result = CooldownAction.CANCEL
        
        self.setWindowTitle("Agent On Cooldown")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Warning header
        header = QLabel(f"⚠  {agent_name} is currently rate-limited")
        header.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(header)
        
        # Cooldown time remaining
        self._time_label = QLabel()
        self._update_time_label()
        self._time_label.setStyleSheet("font-size: 14px; color: rgba(237, 239, 245, 200);")
        layout.addWidget(self._time_label)
        
        # Reason
        if watch_state.cooldown_reason:
            reason_label = QLabel(f"Reason: {watch_state.cooldown_reason[:100]}")
            reason_label.setStyleSheet("font-size: 12px; color: rgba(237, 239, 245, 160);")
            reason_label.setWordWrap(True)
            layout.addWidget(reason_label)
        
        # Options card
        options_card = GlassCard()
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(15, 15, 15, 15)
        options_layout.setSpacing(10)
        
        options_title = QLabel("Options:")
        options_title.setStyleSheet("font-weight: 600;")
        options_layout.addWidget(options_title)
        
        if fallback_agent_name:
            fallback_text = QLabel(
                f"• Use Fallback Agent ({fallback_agent_name})\n"
                "  Run this task with the next agent in your\n"
                "  fallback chain. This won't change your default."
            )
        else:
            fallback_text = QLabel(
                "• Use Fallback Agent (None Available)\n"
                "  No fallback agent configured."
            )
        fallback_text.setStyleSheet("font-size: 12px;")
        options_layout.addWidget(fallback_text)
        
        bypass_text = QLabel(
            "• Bypass Cooldown\n"
            "  Attempt to run anyway. The agent may still\n"
            "  fail if rate-limited."
        )
        bypass_text.setStyleSheet("font-size: 12px;")
        options_layout.addWidget(bypass_text)
        
        cancel_text = QLabel(
            "• Cancel\n"
            "  Don't start this task now."
        )
        cancel_text.setStyleSheet("font-size: 12px;")
        options_layout.addWidget(cancel_text)
        
        layout.addWidget(options_card)
        
        # Buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch()
        
        fallback_btn = QPushButton("Use Fallback")
        fallback_btn.setEnabled(bool(fallback_agent_name))
        fallback_btn.clicked.connect(self._on_use_fallback)
        button_row.addWidget(fallback_btn)
        
        bypass_btn = QPushButton("Bypass")
        bypass_btn.clicked.connect(self._on_bypass)
        button_row.addWidget(bypass_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel)
        button_row.addWidget(cancel_btn)
        
        layout.addLayout(button_row)
        
        # Update time every second
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_time_label)
        self._timer.start(1000)  # 1 second
    
    
    def _update_time_label(self) -> None:
        """Update cooldown time remaining label."""
        remaining = self._watch_state.cooldown_seconds_remaining()
        if remaining <= 0:
            self._time_label.setText("Cooldown Time Remaining: Expired")
        else:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            if minutes > 0:
                self._time_label.setText(
                    f"Cooldown Time Remaining: {minutes}m {seconds}s"
                )
            else:
                self._time_label.setText(
                    f"Cooldown Time Remaining: {seconds} seconds"
                )
    
    
    def _on_use_fallback(self) -> None:
        """Handle Use Fallback button."""
        self._result = CooldownAction.USE_FALLBACK
        self.accept()
    
    
    def _on_bypass(self) -> None:
        """Handle Bypass button."""
        self._result = CooldownAction.BYPASS
        self.accept()
    
    
    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self._result = CooldownAction.CANCEL
        self.reject()
    
    
    def get_result(self) -> str:
        """Get user's choice."""
        return self._result
```


### 3.2 Integration Point: Run Agent Button

**File:** `agents_runner/ui/main_window_tasks_agent.py`

**Current Flow:**
```
User clicks "Run Agent"
    ↓
_start_task_from_ui() called (line 81)
    ↓
Validate inputs (Docker, prompt, environment)
    ↓
Create task, worker, thread
    ↓
Start execution
```

**New Flow with Cooldown Check:**
```
User clicks "Run Agent"
    ↓
_start_task_from_ui() called (line 81)
    ↓
Validate inputs (Docker, prompt, environment)
    ↓
*** CHECK COOLDOWN (NEW) ***
    ├─ If on cooldown:
    │   ├─ Show CooldownModal
    │   ├─ If USE_FALLBACK: override agent for this task
    │   ├─ If BYPASS: clear cooldown, continue
    │   └─ If CANCEL: return early
    └─ If not on cooldown: continue normally
    ↓
Create task, worker, thread
    ↓
Start execution
```

**Implementation:**

```python
# agents_runner/ui/main_window_tasks_agent.py

# Add imports
from agents_runner.core.agent.watch_state import AgentWatchState
from agents_runner.ui.dialogs.cooldown_modal import CooldownModal, CooldownAction

# In _start_task_from_ui(), after line 150 (validation complete):

# Check cooldown for selected agent
agent_cli = environment.agent_selection.agents[0].agent_cli if environment.agent_selection else self.agent_cli
watch_state = self.watch_states.get(agent_cli)

if watch_state and watch_state.is_on_cooldown():
    # Get fallback agent name
    fallback_name = None
    if environment.agent_selection and environment.agent_selection.agent_fallbacks:
        primary_id = environment.agent_selection.agents[0].agent_id
        fallback_id = environment.agent_selection.agent_fallbacks.get(primary_id)
        if fallback_id:
            fallback_agent = next(
                (a for a in environment.agent_selection.agents if a.agent_id == fallback_id),
                None
            )
            if fallback_agent:
                fallback_name = fallback_agent.agent_cli.capitalize()
    
    # Show cooldown modal
    modal = CooldownModal(
        self,
        agent_name=agent_cli.capitalize(),
        watch_state=watch_state,
        fallback_agent_name=fallback_name,
    )
    
    result = modal.exec()
    action = modal.get_result()
    
    if action == CooldownAction.CANCEL:
        return  # Don't start task
    
    elif action == CooldownAction.BYPASS:
        # Clear cooldown and continue with original agent
        from agents_runner.core.agent.rate_limit import RateLimitDetector
        RateLimitDetector.clear_cooldown(watch_state)
        self._save_state()  # Persist cooldown clear
    
    elif action == CooldownAction.USE_FALLBACK:
        # Override agent for this task only (task-scoped)
        if fallback_agent:
            # Create agent selection override
            # This is passed to supervisor, doesn't modify environment
            agent_selection_override = AgentSelection(
                agents=[fallback_agent],
                selection_mode="round-robin",
                agent_fallbacks={},
            )
            # Pass to task creation...
```

---

## Part 4: Proactive Usage Watching (MAY SHIP)

### 4.1 Plugin Architecture

**File:** `agents_runner/core/agent/watchers/base.py` (NEW)

```python
# agents_runner/core/agent/watchers/base.py

from __future__ import annotations

from abc import ABC, abstractmethod
from agents_runner.core.agent.watch_state import AgentWatchState


class AgentWatcher(ABC):
    """Base class for agent usage watchers."""
    
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name (codex, claude, etc.)."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if watcher can run (auth present, API reachable, etc.)."""
        pass
    
    @abstractmethod
    def fetch_usage(self) -> AgentWatchState:
        """Fetch current usage/quota state.
        
        Returns:
            AgentWatchState with updated windows and status
        
        Raises:
            WatcherError: If fetch fails
        """
        pass
    
    @abstractmethod
    def support_level(self) -> str:
        """Get support level (full, best_effort, unknown)."""
        pass


class WatcherError(Exception):
    """Raised when watcher fails to fetch usage."""
    pass
```

### 4.2 OpenAI Codex Watcher (MUST SHIP)

**Research Summary:**
- **Endpoint:** GET `/wham/usage` or `/api/codex/usage` (from report)
- **Auth:** Read from `~/.codex/auth.json` (JWT token or API key)
- **Response:** Contains primary_window (5h) and secondary_window (weekly)
- **Display:** "5h: X% left • weekly: Y% left"

**File:** `agents_runner/core/agent/watchers/codex.py` (NEW)

```python
# agents_runner/core/agent/watchers/codex.py

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from agents_runner.core.agent.watch_state import (
    AgentStatus,
    AgentWatchState,
    SupportLevel,
    UsageWindow,
)
from agents_runner.core.agent.watchers.base import AgentWatcher, WatcherError


class CodexWatcher(AgentWatcher):
    """Watcher for OpenAI Codex usage/quota."""
    
    # API configuration
    API_BASE = "https://api.openai.com"  # TODO: Verify correct endpoint
    USAGE_ENDPOINT = "/wham/usage"  # or /api/codex/usage
    
    # Auth file location
    AUTH_FILE = "~/.codex/auth.json"
    
    def provider_name(self) -> str:
        return "codex"
    
    def support_level(self) -> str:
        return SupportLevel.FULL.value
    
    def is_available(self) -> bool:
        """Check if auth file exists."""
        auth_path = os.path.expanduser(self.AUTH_FILE)
        return os.path.exists(auth_path)
    
    def fetch_usage(self) -> AgentWatchState:
        """Fetch Codex usage from API."""
        # Load auth
        auth_data = self._load_auth()
        if not auth_data:
            raise WatcherError("Auth file not found or invalid")
        
        token = auth_data.get("token") or auth_data.get("api_key")
        if not token:
            raise WatcherError("No token found in auth file")
        
        # Make request
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        try:
            url = f"{self.API_BASE}{self.USAGE_ENDPOINT}"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise WatcherError(f"API request failed: {exc}") from exc
        
        # Parse response
        return self._parse_response(data)
    
    def _load_auth(self) -> dict:
        """Load auth data from ~/.codex/auth.json."""
        auth_path = os.path.expanduser(self.AUTH_FILE)
        try:
            with open(auth_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    
    def _parse_response(self, data: dict) -> AgentWatchState:
        """Parse API response into AgentWatchState.
        
        Expected response structure (RESEARCH NEEDED):
        {
            "primary_window": {
                "name": "5h",
                "used": 45,
                "limit": 100,
                "remaining": 55,
                "reset_at": "2025-01-07T18:00:00Z"
            },
            "secondary_window": {
                "name": "weekly",
                "used": 230,
                "limit": 500,
                "remaining": 270,
                "reset_at": "2025-01-14T00:00:00Z"
            }
        }
        """
        windows = []
        
        # Parse primary window (5h)
        primary = data.get("primary_window", {})
        if primary:
            used = primary.get("used", 0)
            limit = primary.get("limit", 0)
            remaining = primary.get("remaining", 0)
            remaining_percent = (remaining / limit * 100) if limit > 0 else 0
            
            reset_at = None
            if primary.get("reset_at"):
                reset_at = datetime.fromisoformat(
                    primary["reset_at"].replace("Z", "+00:00")
                )
            
            windows.append(UsageWindow(
                name="5h",
                used=used,
                limit=limit,
                remaining=remaining,
                remaining_percent=remaining_percent,
                reset_at=reset_at,
            ))
        
        # Parse secondary window (weekly)
        secondary = data.get("secondary_window", {})
        if secondary:
            used = secondary.get("used", 0)
            limit = secondary.get("limit", 0)
            remaining = secondary.get("remaining", 0)
            remaining_percent = (remaining / limit * 100) if limit > 0 else 0
            
            reset_at = None
            if secondary.get("reset_at"):
                reset_at = datetime.fromisoformat(
                    secondary["reset_at"].replace("Z", "+00:00")
                )
            
            windows.append(UsageWindow(
                name="weekly",
                used=used,
                limit=limit,
                remaining=remaining,
                remaining_percent=remaining_percent,
                reset_at=reset_at,
            ))
        
        # Determine status
        status = AgentStatus.READY
        if windows:
            primary_remaining = windows[0].remaining_percent
            if primary_remaining == 0:
                status = AgentStatus.QUOTA_EXHAUSTED
            elif primary_remaining < 10:
                status = AgentStatus.QUOTA_LOW
        
        return AgentWatchState(
            provider_name="codex",
            support_level=SupportLevel.FULL,
            status=status,
            windows=windows,
            last_checked_at=datetime.now(timezone.utc),
            last_error="",
            raw_data=data,
        )
```

### 4.3 Claude Code Watcher (RESEARCH + IMPLEMENT)

**Research Tasks:**
1. Does Claude Code CLI expose usage/quota API?
2. Check `claude --help` for usage/quota commands
3. Check `~/.claude/` directory for config files with quota info
4. Search Claude Code documentation for API/CLI reference
5. Test if `claude whoami` or similar command returns quota info

**Fallback Approach (if no API):**
```python
# agents_runner/core/agent/watchers/claude.py

class ClaudeWatcher(AgentWatcher):
    """Best-effort watcher for Claude Code."""
    
    def provider_name(self) -> str:
        return "claude"
    
    def support_level(self) -> str:
        return SupportLevel.BEST_EFFORT.value  # No API available
    
    def is_available(self) -> bool:
        """Check if Claude CLI is installed."""
        import shutil
        return shutil.which("claude") is not None
    
    def fetch_usage(self) -> AgentWatchState:
        """Best-effort: check if Claude CLI is accessible."""
        # Try running `claude --version` to check if working
        import subprocess
        
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                status = AgentStatus.READY
            else:
                status = AgentStatus.UNAVAILABLE
        except (subprocess.TimeoutExpired, FileNotFoundError):
            status = AgentStatus.UNAVAILABLE
        
        return AgentWatchState(
            provider_name="claude",
            support_level=SupportLevel.BEST_EFFORT,
            status=status,
            windows=[],  # No usage data available
            last_checked_at=datetime.now(timezone.utc),
            last_error="No usage API available",
        )
```

### 4.4 GitHub Copilot Watcher (RESEARCH + IMPLEMENT)

**Research Tasks:**
1. Does `gh copilot` expose usage/quota commands?
2. Check `gh copilot --help` for usage/limits
3. Search GitHub CLI extension documentation
4. Check for quota headers in API responses (if accessible)

**Implementation Skeleton:**
```python
# agents_runner/core/agent/watchers/copilot.py

class CopilotWatcher(AgentWatcher):
    """Watcher for GitHub Copilot usage/quota."""
    
    def provider_name(self) -> str:
        return "copilot"
    
    def support_level(self) -> str:
        # TODO: Update after research
        return SupportLevel.UNKNOWN.value
    
    def is_available(self) -> bool:
        """Check if gh CLI and copilot extension installed."""
        import subprocess
        
        try:
            result = subprocess.run(
                ["gh", "copilot", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def fetch_usage(self) -> AgentWatchState:
        """Fetch Copilot usage (RESEARCH NEEDED)."""
        # TODO: Implement based on research findings
        raise WatcherError("Not yet implemented - research needed")
```

### 4.5 Google Gemini Watcher (RESEARCH + IMPLEMENT)

**Research Tasks:**
1. Does Gemini CLI expose usage/quota commands?
2. Check `gemini --help` for usage/limits
3. Check Google Cloud Console for quota APIs
4. Search Gemini API documentation for usage endpoints

**Implementation Skeleton:**
```python
# agents_runner/core/agent/watchers/gemini.py

class GeminiWatcher(AgentWatcher):
    """Watcher for Google Gemini usage/quota."""
    
    def provider_name(self) -> str:
        return "gemini"
    
    def support_level(self) -> str:
        # TODO: Update after research
        return SupportLevel.UNKNOWN.value
    
    def is_available(self) -> bool:
        """Check if Gemini CLI is installed."""
        import shutil
        return shutil.which("gemini") is not None
    
    def fetch_usage(self) -> AgentWatchState:
        """Fetch Gemini usage (RESEARCH NEEDED)."""
        # TODO: Implement based on research findings
        raise WatcherError("Not yet implemented - research needed")
```

### 4.6 Watcher Registry

**File:** `agents_runner/core/agent/watchers/registry.py` (NEW)

```python
# agents_runner/core/agent/watchers/registry.py

from __future__ import annotations

from agents_runner.core.agent.watchers.base import AgentWatcher
from agents_runner.core.agent.watchers.codex import CodexWatcher
from agents_runner.core.agent.watchers.claude import ClaudeWatcher
from agents_runner.core.agent.watchers.copilot import CopilotWatcher
from agents_runner.core.agent.watchers.gemini import GeminiWatcher


class WatcherRegistry:
    """Registry of available agent watchers."""
    
    _watchers: dict[str, AgentWatcher] = {}
    
    @classmethod
    def register_defaults(cls) -> None:
        """Register all built-in watchers."""
        cls.register(CodexWatcher())
        cls.register(ClaudeWatcher())
        cls.register(CopilotWatcher())
        cls.register(GeminiWatcher())
    
    @classmethod
    def register(cls, watcher: AgentWatcher) -> None:
        """Register a watcher."""
        cls._watchers[watcher.provider_name()] = watcher
    
    @classmethod
    def get(cls, provider_name: str) -> AgentWatcher | None:
        """Get watcher for provider."""
        return cls._watchers.get(provider_name)
    
    @classmethod
    def all_watchers(cls) -> list[AgentWatcher]:
        """Get all registered watchers."""
        return list(cls._watchers.values())


# Initialize on import
WatcherRegistry.register_defaults()
```

---

## Part 5: Polling Strategy (MAY SHIP)

### 5.1 When to Poll

**Polling Triggers:**
1. **Agent selected** - When user selects environment with agent in UI
2. **Task running** - While task is actively running with agent
3. **Manual refresh** - User clicks "Refresh" button in settings/environment editor
4. **App startup** - Initial poll on app launch (background)

**Polling Interval:** 30 minutes (1800 seconds)

**Avoid Redundant Polls:**
- Don't poll if last check was < 5 minutes ago
- Don't poll if agent not configured/installed
- Don't poll if watcher unavailable

### 5.2 Polling Service

**File:** `agents_runner/core/agent/watch_service.py` (NEW)

```python
# agents_runner/core/agent/watch_service.py

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from agents_runner.core.agent.watch_state import AgentWatchState
from agents_runner.core.agent.watchers.registry import WatcherRegistry
from agents_runner.core.agent.watchers.base import WatcherError


class WatchService:
    """Background service for polling agent usage/quota."""
    
    def __init__(
        self,
        watch_states: dict[str, AgentWatchState],
        on_update: Callable[[str, AgentWatchState], None],
    ) -> None:
        """Initialize watch service.
        
        Args:
            watch_states: Dict of watch states (shared with UI)
            on_update: Callback when watch state updates (provider_name, state)
        """
        self._watch_states = watch_states
        self._on_update = on_update
        self._active_agents: set[str] = set()
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
    
    def start(self) -> None:
        """Start polling service."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop polling service."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def add_agent(self, provider_name: str) -> None:
        """Add agent to active polling list."""
        with self._lock:
            self._active_agents.add(provider_name)
    
    def remove_agent(self, provider_name: str) -> None:
        """Remove agent from active polling list."""
        with self._lock:
            self._active_agents.discard(provider_name)
    
    def poll_now(self, provider_name: str) -> None:
        """Force immediate poll for agent."""
        self._poll_agent(provider_name)
    
    def _poll_loop(self) -> None:
        """Main polling loop (runs in background thread)."""
        while self._running:
            # Poll all active agents
            with self._lock:
                agents_to_poll = list(self._active_agents)
            
            for provider_name in agents_to_poll:
                self._poll_agent(provider_name)
            
            # Sleep for 30 minutes
            for _ in range(1800):  # 1800 seconds = 30 minutes
                if not self._running:
                    break
                time.sleep(1)
    
    def _poll_agent(self, provider_name: str) -> None:
        """Poll single agent usage."""
        # Check if already polled recently
        current_state = self._watch_states.get(provider_name)
        if current_state and current_state.last_checked_at:
            elapsed = datetime.now(timezone.utc) - current_state.last_checked_at
            if elapsed < timedelta(minutes=5):
                # Skip, polled < 5 minutes ago
                return
        
        # Get watcher
        watcher = WatcherRegistry.get(provider_name)
        if not watcher:
            return
        
        # Check if watcher available
        if not watcher.is_available():
            # Update state to unavailable
            state = AgentWatchState(
                provider_name=provider_name,
                support_level=watcher.support_level(),
                status="unavailable",
            )
            self._watch_states[provider_name] = state
            self._on_update(provider_name, state)
            return
        
        # Fetch usage
        try:
            state = watcher.fetch_usage()
            self._watch_states[provider_name] = state
            self._on_update(provider_name, state)
        except WatcherError as exc:
            # Update state with error
            if not current_state:
                current_state = AgentWatchState(provider_name=provider_name)
            current_state.last_error = str(exc)
            current_state.last_checked_at = datetime.now(timezone.utc)
            self._watch_states[provider_name] = current_state
            self._on_update(provider_name, current_state)
```


---

## Part 6: UI Integration (MAY SHIP)

### 6.1 Where to Display Usage Badges

**Option 1: Settings Page (RECOMMENDED)**
- New section: "Agent Status"
- Table with columns: Agent | Status | Usage | Actions
- Shows all configured agents
- [Refresh] button to poll now
- Always accessible, doesn't clutter task flow

**Option 2: Environment Editor (Agents Tab)**
- Show usage badge next to each agent in agent list
- Updates when environment selected
- Good visibility, but requires environment selection

**Option 3: New Task Page**
- Show usage badge next to agent selector
- Updates when environment selected
- Most visible, but clutters task creation UI

**Recommendation:** Start with Settings Page, add to Environment Editor later.

### 6.2 Settings Page Integration

**File:** `agents_runner/ui/pages/settings.py`

**Add after line 200 (after preflight section):**

```python
# Agent Status Section
agent_status_label = QLabel("Agent Status")
agent_status_label.setStyleSheet("font-size: 14px; font-weight: 650;")
grid.addWidget(agent_status_label, row, 0, 1, 4)
row += 1

# Agent status table
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView

self._agent_status_table = QTableWidget()
self._agent_status_table.setColumnCount(4)
self._agent_status_table.setHorizontalHeaderLabels(["Agent", "Status", "Usage", "Actions"])
self._agent_status_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
self._agent_status_table.setRowCount(4)

# Populate with agents
agents = [
    ("OpenAI Codex", "codex"),
    ("Claude Code", "claude"),
    ("GitHub Copilot", "copilot"),
    ("Google Gemini", "gemini"),
]

for i, (display_name, provider_name) in enumerate(agents):
    self._agent_status_table.setItem(i, 0, QTableWidgetItem(display_name))
    self._agent_status_table.setItem(i, 1, QTableWidgetItem("Checking..."))
    self._agent_status_table.setItem(i, 2, QTableWidgetItem("Unknown"))
    
    # Refresh button
    refresh_btn = QPushButton("Refresh")
    refresh_btn.clicked.connect(lambda checked=False, p=provider_name: self._refresh_agent_status(p))
    self._agent_status_table.setCellWidget(i, 3, refresh_btn)

grid.addWidget(self._agent_status_table, row, 0, 1, 4)
row += 1

# Add method to update status
def _refresh_agent_status(self, provider_name: str) -> None:
    """Refresh status for single agent."""
    # Emit signal to main window to poll now
    self.refresh_agent_status_requested.emit(provider_name)

def _update_agent_status_display(self, provider_name: str, watch_state: AgentWatchState) -> None:
    """Update agent status table with new watch state."""
    # Find row for this agent
    agent_map = {"codex": 0, "claude": 1, "copilot": 2, "gemini": 3}
    row = agent_map.get(provider_name, -1)
    if row < 0:
        return
    
    # Update status column
    status_text = watch_state.status.value.replace("_", " ").title()
    if watch_state.is_on_cooldown():
        remaining = watch_state.cooldown_seconds_remaining()
        status_text = f"On Cooldown ({int(remaining)}s)"
    self._agent_status_table.item(row, 1).setText(status_text)
    
    # Update usage column
    usage_text = watch_state.all_windows_display()
    self._agent_status_table.item(row, 2).setText(usage_text)
```

### 6.3 Main Window Integration

**File:** `agents_runner/ui/main_window.py`

**Add to __init__():**

```python
# Initialize watch states
self.watch_states: dict[str, AgentWatchState] = {}

# Initialize watch service
from agents_runner.core.agent.watch_service import WatchService
self.watch_service = WatchService(
    watch_states=self.watch_states,
    on_update=self._on_watch_state_update,
)
self.watch_service.start()

# Load persisted watch states
from agents_runner.persistence import load_watch_state
self.watch_states.update(load_watch_state(self.state))
```

**Add method:**

```python
def _on_watch_state_update(self, provider_name: str, watch_state: AgentWatchState) -> None:
    """Handle watch state update from polling service."""
    # Update UI (if settings page visible)
    if hasattr(self, '_settings_page'):
        self._settings_page._update_agent_status_display(provider_name, watch_state)
    
    # Save to persistence
    from agents_runner.persistence import save_watch_state
    save_watch_state(self.state, self.watch_states)
    self._save_state()
```

**Add to closeEvent():**

```python
def closeEvent(self, event: QCloseEvent) -> None:
    # Stop watch service
    if hasattr(self, 'watch_service'):
        self.watch_service.stop()
    
    # ... existing cleanup ...
```

---

## Part 7: Error Handling

### 7.1 Network Failures

**Scenario:** Watcher API request times out or fails

**Handling:**
- Catch `requests.RequestException` in watcher
- Update watch_state.last_error with error message
- Don't block UI or task execution
- Show error in status table with [Retry] button
- Log error for debugging

**Example:**

```python
try:
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
except requests.Timeout:
    watch_state.last_error = "Request timed out"
    watch_state.status = AgentStatus.UNKNOWN
except requests.RequestException as exc:
    watch_state.last_error = f"Network error: {exc}"
    watch_state.status = AgentStatus.UNKNOWN
```

### 7.2 Auth Errors

**Scenario:** Auth file missing, expired, or invalid

**Handling:**
- Check for auth file existence before API call
- If missing: update status to "Login needed" (non-fatal)
- If expired: attempt refresh (if refresh token available)
- Show clear message in UI: "Login required - click to authenticate"
- Don't block usage, just show unknown status

**Example:**

```python
if not os.path.exists(auth_file):
    return AgentWatchState(
        provider_name=self.provider_name(),
        status=AgentStatus.UNAVAILABLE,
        last_error="Login required - run 'codex login'",
    )
```

### 7.3 API Schema Changes

**Scenario:** API response format changes unexpectedly

**Handling:**
- Wrap response parsing in try/except
- If parsing fails, log raw response for debugging
- Update watch_state.last_error with parse error
- Gracefully degrade to UNKNOWN status
- Don't crash application

**Example:**

```python
try:
    windows = self._parse_response(data)
except (KeyError, ValueError, TypeError) as exc:
    return AgentWatchState(
        provider_name=self.provider_name(),
        status=AgentStatus.UNKNOWN,
        last_error=f"Failed to parse API response: {exc}",
        raw_data=data,  # Preserve for debugging
    )
```

### 7.4 Watcher Unavailable

**Scenario:** Watcher not implemented or agent not installed

**Handling:**
- `is_available()` returns False
- Show "Not Available" in status column
- Disable [Refresh] button for this agent
- Don't attempt polling
- Still allow task execution (best-effort fallback)

---

## Part 8: File Structure

### 8.1 New Files

```
agents_runner/
├── core/
│   └── agent/
│       ├── watch_state.py (NEW, ~150 lines)
│       │   └── AgentWatchState, SupportLevel, AgentStatus, UsageWindow
│       ├── rate_limit.py (NEW, ~200 lines)
│       │   └── RateLimitDetector
│       ├── watch_service.py (NEW, ~200 lines)
│       │   └── WatchService (polling)
│       └── watchers/
│           ├── __init__.py (NEW)
│           ├── base.py (NEW, ~50 lines)
│           │   └── AgentWatcher, WatcherError
│           ├── registry.py (NEW, ~50 lines)
│           │   └── WatcherRegistry
│           ├── codex.py (NEW, ~200 lines)
│           │   └── CodexWatcher
│           ├── claude.py (NEW, ~100 lines)
│           │   └── ClaudeWatcher (best-effort)
│           ├── copilot.py (NEW, ~100 lines)
│           │   └── CopilotWatcher (research needed)
│           └── gemini.py (NEW, ~100 lines)
│               └── GeminiWatcher (research needed)
└── ui/
    └── dialogs/
        └── cooldown_modal.py (NEW, ~200 lines)
            └── CooldownModal, CooldownAction
```

**Total New Lines:** ~1,350 lines

### 8.2 Modified Files

```
agents_runner/
├── persistence.py (ADD ~100 lines)
│   └── load_watch_state(), save_watch_state()
├── execution/
│   └── supervisor.py (ADD ~50 lines)
│       └── Integrate rate-limit detection + cooldown recording
├── ui/
│   ├── main_window.py (ADD ~30 lines)
│   │   └── Initialize watch_service, handle updates
│   ├── main_window_tasks_agent.py (ADD ~80 lines)
│   │   └── Cooldown check before task start
│   └── pages/
│       └── settings.py (ADD ~100 lines)
│           └── Agent status section + table
```

**Total Modified Lines:** ~360 lines

**Grand Total:** ~1,710 lines (new + modifications)

---

## Part 9: Implementation Plan

### 9.1 Phase 1: Core Infrastructure (Days 1-2)

**Priority:** MUST SHIP

**Tasks:**
1. Create `watch_state.py` with data models
2. Add persistence functions (`load_watch_state`, `save_watch_state`)
3. Create `rate_limit.py` with RateLimitDetector
4. Integrate RateLimitDetector into supervisor
5. Test rate-limit detection with mock logs

**Deliverables:**
- Rate-limit detection working
- Cooldown state persisted
- Supervisor records cooldowns

**Testing:**
- Unit tests for RateLimitDetector.detect()
- Integration test: simulate rate-limit error, verify cooldown recorded

### 9.2 Phase 2: Cooldown Modal (Days 3-4)

**Priority:** MUST SHIP

**Tasks:**
1. Create `cooldown_modal.py` with CooldownModal UI
2. Integrate modal into `main_window_tasks_agent.py`
3. Implement cooldown check before task start
4. Implement fallback selection (task-scoped)
5. Implement bypass functionality

**Deliverables:**
- Modal appears when agent on cooldown
- Use Fallback button works correctly
- Bypass button clears cooldown
- Cancel button stops task launch

**Testing:**
- Manual test: trigger cooldown, verify modal appears
- Test each button action
- Verify fallback is task-scoped (doesn't change environment)

### 9.3 Phase 3: Watcher Plugin System (Days 5-6)

**Priority:** MAY SHIP (Codex only for initial release)

**Tasks:**
1. Create watcher plugin architecture (`base.py`, `registry.py`)
2. Implement CodexWatcher (requires research on API endpoint)
3. Create WatchService for polling
4. Integrate watch_service into main window
5. Test Codex usage fetching

**Deliverables:**
- CodexWatcher fetches usage from API
- WatchService polls every 30 minutes
- Watch states updated and persisted

**Testing:**
- Mock Codex API responses
- Test polling interval
- Test error handling (auth missing, API down)

### 9.4 Phase 4: UI Integration (Day 7)

**Priority:** MAY SHIP

**Tasks:**
1. Add agent status section to Settings page
2. Implement status table with usage display
3. Add [Refresh] button functionality
4. Wire watch state updates to UI
5. Test UI updates on polling

**Deliverables:**
- Settings page shows agent status
- Usage badges display correctly
- Manual refresh works
- Live updates on polling

**Testing:**
- Manual test: refresh agent, verify UI updates
- Test with multiple agents
- Test cooldown display in status table

### 9.5 Phase 5: Additional Watchers (Days 8-10)

**Priority:** OPTIONAL (Post-launch enhancement)

**Tasks:**
1. Research Claude Code usage API (if available)
2. Research Copilot usage API (if available)
3. Research Gemini usage API (if available)
4. Implement watchers for agents with APIs
5. Implement best-effort watchers for agents without APIs

**Deliverables:**
- ClaudeWatcher (best-effort or full, based on research)
- CopilotWatcher (best-effort or full, based on research)
- GeminiWatcher (best-effort or full, based on research)

**Testing:**
- Test each watcher with real CLI
- Verify graceful degradation when unavailable

---

## Part 10: Research Checklist

### 10.1 OpenAI Codex API Research

**Status:** PARTIALLY KNOWN

**Known:**
- Endpoint exists: `/wham/usage` or `/api/codex/usage`
- Auth from `~/.codex/auth.json`
- Response has primary_window (5h) and secondary_window (weekly)

**Need to Research:**
1. Exact API endpoint URL (base domain + path)
2. Auth token format (JWT? API key? OAuth?)
3. Auth token location in auth.json (key name)
4. Response schema (exact JSON structure)
5. Rate limits for usage API itself
6. How to detect expired auth
7. Refresh token mechanism (if applicable)

**How to Research:**
- Run `codex login` and inspect `~/.codex/auth.json`
- Use network inspector to capture API calls
- Check Codex CLI source code (if open source)
- Read official Codex API documentation

### 10.2 Claude Code API Research

**Status:** UNKNOWN

**Need to Research:**
1. Does Claude Code CLI expose usage/quota commands?
2. Check `claude --help` for usage-related commands
3. Check `~/.claude/` directory structure
4. Does `claude whoami` return quota info?
5. Are there any hidden CLI flags for usage? (`claude --usage`, etc.)
6. Does Claude API have usage endpoints? (api.anthropic.com)
7. Check Claude Code documentation for rate limits

**How to Research:**
- Run `claude --help | grep -i usage`
- Run `claude whoami` and check output
- Inspect `~/.claude/` directory
- Read Anthropic API documentation
- Search for Claude Code CLI reference

### 10.3 GitHub Copilot API Research

**Status:** UNKNOWN

**Need to Research:**
1. Does `gh copilot` have usage commands?
2. Check `gh copilot --help` for quota/limits
3. Does GitHub CLI expose rate limit headers?
4. Are there GitHub API endpoints for Copilot usage?
5. Check `.copilot/` directory for config files
6. Does Copilot have per-hour or per-day limits?

**How to Research:**
- Run `gh copilot --help | grep -i usage`
- Run `gh api rate_limit` (GitHub API rate limits)
- Check GitHub Copilot documentation
- Inspect network requests from `gh copilot` commands

### 10.4 Google Gemini API Research

**Status:** UNKNOWN

**Need to Research:**
1. Does Gemini CLI expose usage commands?
2. Check `gemini --help` for quota/limits
3. Does Google Cloud Console show Gemini quotas?
4. Are there Gemini API usage endpoints?
5. Check `~/.gemini/` directory structure
6. What are Gemini rate limits (requests per minute, per day)?

**How to Research:**
- Run `gemini --help | grep -i usage`
- Check Google Cloud Console → APIs & Services → Quotas
- Read Gemini API documentation
- Search for Gemini CLI usage docs

---

## Part 11: Success Criteria

### 11.1 MUST SHIP (Core Functionality)

- [ ] Rate-limit errors detected from logs and exit codes
- [ ] Cooldown state tracked per agent
- [ ] Cooldown state persisted across app restarts
- [ ] Cooldown modal appears when user clicks "Run Agent" on cooldown agent
- [ ] "Use Fallback" button works and is task-scoped only
- [ ] "Bypass" button clears cooldown and allows execution
- [ ] "Cancel" button stops task from starting
- [ ] Cooldown countdown updates every second in modal
- [ ] No false positives for rate-limit detection (high-confidence patterns)
- [ ] Cooldown check happens ONLY on "Run Agent" click, not earlier

### 11.2 MAY SHIP (Enhancement Features)

- [ ] OpenAI Codex watcher fetches usage from API
- [ ] Usage badges display in Settings page
- [ ] Manual refresh button works
- [ ] Polling service runs every 30 minutes
- [ ] Watch states update UI automatically
- [ ] Claude/Copilot/Gemini watchers implemented (best-effort or full)
- [ ] Proactive warning when quota < 10%
- [ ] Usage display in Environment editor (Agents tab)

### 11.3 Quality Criteria

- [ ] All new files under 300 lines (soft limit)
- [ ] No file exceeds 600 lines (hard limit)
- [ ] Error handling for all network/auth failures
- [ ] Graceful degradation when watchers unavailable
- [ ] No blocking UI operations (polling in background thread)
- [ ] Clear error messages for users
- [ ] Unit tests for RateLimitDetector
- [ ] Integration tests for cooldown flow
- [ ] Documentation for watcher plugin system

---

## Part 12: Risk Assessment

### 12.1 High-Risk Areas

**Risk:** False positive rate-limit detection  
**Impact:** Unnecessary cooldowns annoy users  
**Mitigation:**
- Use conservative regex patterns (high confidence)
- Always provide Bypass button
- Log all detections for debugging
- Tunable patterns per agent (can update without code changes)

**Risk:** Codex API endpoint incorrect or auth format wrong  
**Impact:** Codex watcher never works  
**Mitigation:**
- Research thoroughly before implementation
- Implement robust error handling
- Fallback to best-effort if API unavailable
- Don't block task execution if watcher fails

**Risk:** Cooldown modal not appearing at correct time  
**Impact:** Users frustrated by inconsistent UX  
**Mitigation:**
- Clear state machine for modal display
- Unit tests for timing logic
- Always check cooldown immediately before task start
- Never cache cooldown check results

### 12.2 Medium-Risk Areas

**Risk:** Polling service consuming too many resources  
**Impact:** Performance degradation  
**Mitigation:**
- 30-minute polling interval (not aggressive)
- Background thread (doesn't block UI)
- Skip poll if last check < 5 minutes ago
- Stop service on app close

**Risk:** Watch state not persisting correctly  
**Impact:** Cooldowns lost across restarts  
**Mitigation:**
- Use existing persistence layer
- Test save/load functions thoroughly
- Include version field for future migrations

**Risk:** Task-scoped fallback not working correctly  
**Impact:** Environment defaults changed unexpectedly  
**Mitigation:**
- Clear separation between task and environment agent selection
- Pass override to supervisor, don't modify environment
- Document behavior clearly in UI

### 12.3 Low-Risk Areas

**Risk:** UI layout issues with new status table  
**Impact:** Visual glitches  
**Mitigation:**
- Follow existing Settings page patterns
- Test on different screen sizes
- Use Qt layout managers

**Risk:** Additional watchers not implemented by deadline  
**Impact:** Only Codex has proactive watching  
**Mitigation:**
- Prioritize cooldown system (core functionality)
- Watchers are enhancement, not blocker
- Best-effort watchers provide value even without API

---

## Part 13: Open Questions

### 13.1 For Stakeholder Decision

1. **Should proactive watching be in initial release?**
   - Option A: Ship cooldown only, add watchers later
   - Option B: Include Codex watcher in initial release
   - Option C: Include all watchers (delays release)
   - **Recommendation:** Option B (core + Codex watcher)

2. **Where should usage badges display?**
   - Option A: Settings page only
   - Option B: Settings + Environment editor
   - Option C: Settings + Environment editor + New Task page
   - **Recommendation:** Option A initially, add B later

3. **Default cooldown duration when not extractable?**
   - Current: 60 seconds
   - Alternative: 120 seconds (more conservative)
   - **Recommendation:** 60 seconds (matches supervisor rate-limit backoff)

4. **Should expired cooldowns auto-clear?**
   - Option A: Auto-clear on expiration
   - Option B: Persist until next check
   - **Recommendation:** Option A (cleaner UX)

### 13.2 For Implementation Research

1. **OpenAI Codex API endpoint:** Needs verification
2. **Claude Code usage API:** Existence unknown
3. **Copilot usage API:** Existence unknown
4. **Gemini usage API:** Existence unknown
5. **Auth token refresh:** Mechanism unclear for all agents

---

## Appendix A: Data Flow Diagrams

### A.1 Cooldown Detection Flow

```
Task Execution Fails
    ↓
Supervisor classifies error
    ↓
ErrorType == RATE_LIMIT?
    ├─ Yes:
    │   ├─ RateLimitDetector.detect(logs, exit_code)
    │   ├─ Extract cooldown duration
    │   ├─ Record in watch_state
    │   ├─ Update persistence
    │   └─ Log event
    └─ No: Continue normal retry/fallback
```

### A.2 Cooldown Check Flow

```
User clicks "Run Agent"
    ↓
Get selected agent
    ↓
Check watch_state for cooldown
    ├─ On cooldown:
    │   ├─ Show CooldownModal
    │   ├─ User chooses:
    │   │   ├─ USE_FALLBACK: Override agent for task
    │   │   ├─ BYPASS: Clear cooldown, continue
    │   │   └─ CANCEL: Return early, don't start
    │   └─ Proceed with user's choice
    └─ Not on cooldown: Continue normally
```

### A.3 Proactive Watching Flow

```
WatchService polling loop (every 30 min)
    ↓
For each active agent:
    ├─ Check last_checked_at
    ├─ Skip if < 5 minutes ago
    ├─ Get watcher from registry
    ├─ Check watcher.is_available()
    │   ├─ Yes: Fetch usage
    │   │   ├─ Parse response
    │   │   ├─ Update watch_state
    │   │   ├─ Persist state
    │   │   └─ Emit UI update
    │   └─ No: Update status to unavailable
    └─ Continue to next agent
```

---

## Appendix B: UI Wireframes

### B.1 Cooldown Modal

```
┌───────────────────────────────────────────────────────────┐
│  Agent On Cooldown                                     [X] │
├───────────────────────────────────────────────────────────┤
│                                                            │
│  ⚠  OpenAI Codex is currently rate-limited                │
│                                                            │
│  Cooldown Time Remaining: 3m 42s                          │
│                                                            │
│  Reason: rate limit exceeded (quota: 0%)                  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Options:                                              │ │
│  │                                                       │ │
│  │ • Use Fallback Agent (Claude Code)                   │ │
│  │   Run this task with the next agent in your          │ │
│  │   fallback chain. This won't change your default.    │ │
│  │                                                       │ │
│  │ • Bypass Cooldown                                    │ │
│  │   Attempt to run anyway. The agent may still         │ │
│  │   fail if rate-limited.                              │ │
│  │                                                       │ │
│  │ • Cancel                                              │ │
│  │   Don't start this task now.                         │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│          [Use Fallback]  [Bypass]  [Cancel]               │
│                                                            │
└───────────────────────────────────────────────────────────┘
```

### B.2 Settings Page - Agent Status Section

```
┌───────────────────────────────────────────────────────────┐
│  Settings                                          [Back]  │
├───────────────────────────────────────────────────────────┤
│                                                            │
│  ... existing settings sections ...                       │
│                                                            │
│  Agent Status                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Agent          │ Status      │ Usage          │ Act  │  │
│  ├────────────────┼─────────────┼────────────────┼──────┤  │
│  │ OpenAI Codex   │ Ready       │ 5h: 45% left   │[Ref] │  │
│  │                │             │ weekly: 72% lft│      │  │
│  ├────────────────┼─────────────┼────────────────┼──────┤  │
│  │ Claude Code    │ Unknown     │ Unknown        │[Ref] │  │
│  ├────────────────┼─────────────┼────────────────┼──────┤  │
│  │ GitHub Copilot │ On Cooldown │ Checking...    │[Ref] │  │
│  │                │ (2m 15s)    │                │      │  │
│  ├────────────────┼─────────────┼────────────────┼──────┤  │
│  │ Google Gemini  │ Unavailable │ Not installed  │[Ref] │  │
│  └────────────────┴─────────────┴────────────────┴──────┘  │
│                                                            │
│  Last updated: 2025-01-07 15:23:45                         │
│                                                            │
└───────────────────────────────────────────────────────────┘
```

---

## Appendix C: Example API Responses

### C.1 OpenAI Codex Usage Response (EXPECTED)

```json
{
  "primary_window": {
    "name": "5h",
    "used": 45,
    "limit": 100,
    "remaining": 55,
    "reset_at": "2025-01-07T20:00:00Z"
  },
  "secondary_window": {
    "name": "weekly",
    "used": 230,
    "limit": 500,
    "remaining": 270,
    "reset_at": "2025-01-14T00:00:00Z"
  },
  "status": "ok"
}
```

### C.2 Rate-Limit Error Examples

**Codex:**
```
Error: rate limit exceeded for model gpt-4-turbo
Please retry after 60 seconds
Quota: 0% remaining (5h window)
```

**Claude:**
```json
{
  "error": {
    "type": "rate_limit_error",
    "message": "Too many requests. Retry after 120 seconds."
  }
}
```

**Copilot:**
```
rate limit exceeded
wait 90 seconds before retrying
```

**Gemini:**
```
Error 429: quota exceeded
Resource exhausted. Try again later.
```

---

## Summary

This design document provides comprehensive implementation guidance for the Usage/Rate Limit Watch System (Task 3). The system is divided into two distinct parts:

1. **MUST SHIP:** Rate-limit detection and cooldown management (reactive)
2. **MAY SHIP:** Proactive usage watching with per-agent plugins

**Estimated Implementation Time:**
- Core (MUST SHIP): 4 days
- Enhancement (MAY SHIP): 6 days
- Total: 10 days with research

**File Impact:**
- New files: ~1,350 lines (10 new files)
- Modified files: ~360 lines (5 modified files)
- Total: ~1,710 lines

**Next Steps:**
1. Get stakeholder approval on scope (core vs full)
2. Research OpenAI Codex API endpoint and auth format
3. Begin Phase 1 implementation (core infrastructure)
4. Test rate-limit detection with mock scenarios
5. Implement cooldown modal UI
6. Integrate into task launch flow

**Critical Success Factors:**
- Conservative rate-limit detection patterns
- Clear cooldown modal UX
- Task-scoped fallback (doesn't change defaults)
- Graceful degradation when watchers unavailable
- No blocking operations (background polling)

---

**Document Status:** COMPLETE - Ready for Review  
**Last Updated:** 2025-01-07  
**Author:** Auditor Mode  
**Review Status:** PENDING

