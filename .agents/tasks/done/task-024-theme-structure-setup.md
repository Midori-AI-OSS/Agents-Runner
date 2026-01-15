# Task 024: Theme Structure Setup

## Parent Task
task-024-organize-theme-implementations (master)

## Description
Create the directory structure and base files for the theme organization refactor. This sets up the foundation for moving each agent's theme implementation into separate modules.

## Specific Actions
- Create directory structure:
  ```
  agents_runner/ui/themes/
    __init__.py
    codex/
      __init__.py
    claude/
      __init__.py
    gemini/
      __init__.py
    copilot/
      __init__.py
  ```
- Create empty `__init__.py` files in each directory
- Add module docstrings to each `__init__.py`:
  - Main themes/__init__.py: "Agent-specific theme implementations for the UI background system."
  - Each agent __init__.py: "Background theme implementation for [Agent] agent."
- Verify directory structure is created correctly

## Code Location
- New directories: `agents_runner/ui/themes/`
- Base file: `agents_runner/ui/graphics.py` (will be modified in subsequent tasks)

## Technical Context
- Follow Python package structure conventions
- Keep __init__.py files minimal (docstring only for now)
- Structure supports future addition of other theme components

## Dependencies
None (first task in series)

## Acceptance Criteria
- All directories created successfully
- All __init__.py files exist and have docstrings
- Directory structure matches specification exactly
- No breaking changes to existing code
