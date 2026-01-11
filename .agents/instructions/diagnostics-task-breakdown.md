# Diagnostics and Crash Reporting - Task Breakdown

## Overview
This document tracks the task breakdown for implementing issue reporting and crash capture functionality.

## Task Dependency Graph

```
Foundation Layer (no dependencies):
├── a7f3e219: Setup diagnostics directory infrastructure
├── b8d4c320: Implement secret redaction utility
├── e1f7f653: Add Report an Issue UI action
├── k7l3m219: Create log file collector module
└── l8m4n320: Create task state collector module

Core Components (depend on foundation):
├── j6k2l108: Implement settings collector with secret filtering
│   └── depends on: b8d4c320
├── c9e5d431: Create diagnostics bundle builder
│   └── depends on: a7f3e219, b8d4c320, j6k2l108, k7l3m219, l8m4n320
├── d0f6e542: Implement crash report writer
│   └── depends on: a7f3e219, b8d4c320
└── i5j1k097: Add breadcrumb logging system
    └── depends on: d0f6e542

UI Integration:
├── f2g8h764: Create diagnostics bundle dialog
│   └── depends on: c9e5d431, e1f7f653
├── g3h9i875: Install crash handler on application startup
│   └── depends on: d0f6e542
└── h4i0j986: Implement crash detection on startup
    └── depends on: g3h9i875

Documentation:
└── m9n5o431: Add diagnostics documentation
    └── depends on: f2g8h764, h4i0j986
```

## Recommended Implementation Order

### Phase 1: Foundation (parallel work possible)
1. a7f3e219: Setup diagnostics directory infrastructure
2. b8d4c320: Implement secret redaction utility
3. k7l3m219: Create log file collector module
4. l8m4n320: Create task state collector module

### Phase 2: Data Collection (after Phase 1)
5. j6k2l108: Implement settings collector with secret filtering

### Phase 3: Core Systems (after Phase 2)
6. c9e5d431: Create diagnostics bundle builder
7. d0f6e542: Implement crash report writer

### Phase 4: UI Components (parallel with Phase 3)
8. e1f7f653: Add Report an Issue UI action

### Phase 5: Enhanced Features
9. i5j1k097: Add breadcrumb logging system

### Phase 6: Integration (after Phases 3-5)
10. f2g8h764: Create diagnostics bundle dialog
11. g3h9i875: Install crash handler on application startup
12. h4i0j986: Implement crash detection on startup

### Phase 7: Documentation (final)
13. m9n5o431: Add diagnostics documentation

## Key Requirements Summary

### A) Report an Issue UI
- Action in UI labeled "Report an Issue"
- Dialog with explanation and two buttons
- No automatic upload/sending

### B) Diagnostics Bundle
- Single zip file with timestamp
- Includes: app info, OS info, Python version, settings (redacted), logs (redacted), task state
- Stored in stable directory: ~/.midoriai/diagnostics/bundles/

### C) Crash Capture
- Global unhandled exception handler
- Crash reports with exception details and stack trace
- Breadcrumb log of recent events
- Notification on next startup if crash detected

### D) Redaction Rules (CRITICAL)
- No secrets in bundles or crash reports
- Redact: authorization headers, bearer tokens, cookies, API keys, access tokens
- Exclude known secret configuration files

## Notes for Coders
- Follow Python 3.13+ with type hints
- Keep files under 300 lines (soft max), 600 lines (hard max)
- Use pathlib for cross-platform paths
- Follow existing patterns in agents_runner/
- Sharp corners only (no rounded borders)
- Commit early and often with clear [TYPE] messages
