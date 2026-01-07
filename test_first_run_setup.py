#!/usr/bin/env python3
"""Test script for first-run setup system."""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from agents_runner.setup.agent_status import detect_all_agents
from agents_runner.setup.commands import get_setup_command
from agents_runner.setup.orchestrator import (
    check_setup_complete,
    load_setup_state,
    mark_setup_skipped,
)


def test_agent_detection():
    """Test agent detection."""
    print("=" * 60)
    print("Testing Agent Detection")
    print("=" * 60)
    
    statuses = detect_all_agents()
    for status in statuses:
        print(f"\nAgent: {status.agent}")
        print(f"  Installed: {status.installed}")
        print(f"  Logged In: {status.logged_in}")
        print(f"  Status: {status.status_text}")
        print(f"  Type: {status.status_type.value}")
        if status.username:
            print(f"  Username: {status.username}")


def test_setup_commands():
    """Test setup commands."""
    print("\n" + "=" * 60)
    print("Testing Setup Commands")
    print("=" * 60)
    
    agents = ["codex", "claude", "copilot", "gemini", "github"]
    for agent in agents:
        cmd = get_setup_command(agent)
        print(f"\n{agent}: {cmd if cmd else '(None - no setup command)'}")


def test_setup_state():
    """Test setup state management."""
    print("\n" + "=" * 60)
    print("Testing Setup State Management")
    print("=" * 60)
    
    print(f"\nSetup complete: {check_setup_complete()}")
    print(f"Current state: {load_setup_state()}")
    
    # Test marking as skipped
    print("\nMarking setup as skipped...")
    mark_setup_skipped()
    
    print(f"Setup complete after skip: {check_setup_complete()}")
    print(f"State after skip: {load_setup_state()}")


def main():
    """Run all tests."""
    test_agent_detection()
    test_setup_commands()
    test_setup_state()
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
