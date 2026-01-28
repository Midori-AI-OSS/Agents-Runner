"""Docker validation utility for first-run setup.

This module provides Docker smoke test functionality to verify that Docker
is properly installed and configured on the system.
"""

import logging
import os
import shutil
import tempfile
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QMessageBox

from agents_runner.terminal_apps import detect_terminal_options, launch_in_terminal

# Constants for Docker validation
DOCKER_IMAGE = "lunamidori5/pixelarch:emerald"
DOCKER_SETUP_URL = "https://io.midori-ai.xyz/support/dockersetup/"
POLL_INTERVAL_MS = 2000
POLL_MAX_COUNT = 60  # 2 minutes timeout (60 * 2000ms = 120000ms = 2 minutes)
TEST_RESULT_FILE = "test-result.txt"

logger = logging.getLogger(__name__)


class DockerValidator:
    """Handles Docker validation smoke tests for first-run setup.
    
    This validator checks if Docker is available and working by:
    1. Verifying docker CLI is in PATH
    2. Pulling the PixelArch image
    3. Running a test container with a simple command
    
    The test runs asynchronously in a terminal window and polls for results.
    """

    def __init__(self, parent: QWidget):
        """Initialize Docker validator.
        
        Args:
            parent: Parent widget for dialogs
        """
        self._parent = parent
        self._test_folder: str | None = None
        self._poll_count = 0
        self._status_callback: Callable[[str, str], None] | None = None
        self._completion_callback: Callable[[bool], None] | None = None

    def start_validation(
        self,
        status_callback: Callable[[str, str], None],
        completion_callback: Callable[[bool], None],
    ) -> bool:
        """Start Docker validation process.
        
        Args:
            status_callback: Callback for status updates (message, color)
            completion_callback: Callback when validation completes (success)
            
        Returns:
            True if validation was started, False if preconditions failed
        """
        self._status_callback = status_callback
        self._completion_callback = completion_callback
        
        # Check if docker is available
        if shutil.which("docker") is None:
            status_callback("✗ Docker CLI not found in PATH", "#f44336")
            self._show_setup_help()
            completion_callback(False)
            return False

        # Create test folder
        try:
            self._test_folder = tempfile.mkdtemp(prefix="docker-check-")
        except OSError as e:
            logger.error(f"Failed to create test folder: {e}")
            status_callback("✗ Failed to create test folder", "#f44336")
            self._show_setup_help()
            completion_callback(False)
            return False
        
        # Launch terminal with docker commands
        terminals = detect_terminal_options()
        if not terminals:
            status_callback("✗ No terminal found on system", "#f44336")
            self._show_setup_help()
            self._cleanup_test_folder()
            completion_callback(False)
            return False

        marker_file = os.path.join(self._test_folder, TEST_RESULT_FILE)
        script = self._generate_test_script(marker_file)
        
        # Try to launch terminal
        terminal_launched = False
        for terminal in terminals:
            try:
                launch_in_terminal(terminal, script, cwd="/tmp")
                terminal_launched = True
                status_callback("⏳ Running Docker test in terminal...", "#2196f3")
                self._poll_count = 0
                QTimer.singleShot(POLL_INTERVAL_MS, self._poll_result)
                break
            except Exception as e:
                logger.warning(f"Failed to launch terminal {terminal}: {e}")
                continue
        
        if not terminal_launched:
            status_callback("✗ Failed to launch terminal", "#f44336")
            self._show_setup_help()
            self._cleanup_test_folder()
            completion_callback(False)
            return False
            
        return True

    def _generate_test_script(self, marker_file: str) -> str:
        """Generate bash script for Docker smoke test.
        
        Args:
            marker_file: Path to result marker file
            
        Returns:
            Bash script as string
        """
        return f"""
echo "=== Docker Smoke Test ==="
echo ""
echo "Step 1: Pulling PixelArch image..."
if docker pull {DOCKER_IMAGE}; then
    echo ""
    echo "Step 2: Running test container..."
    if docker run --rm {DOCKER_IMAGE} /bin/bash -lc 'echo hello world'; then
        echo ""
        echo "✓ Docker test PASSED"
        echo "success" > "{marker_file}"
    else
        echo ""
        echo "✗ Docker test FAILED: Container execution failed"
        echo "fail" > "{marker_file}"
    fi
else
    echo ""
    echo "✗ Docker test FAILED: Image pull failed"
    echo "fail" > "{marker_file}"
fi
echo ""
echo "Press Enter to close..."
read
"""

    def _poll_result(self) -> None:
        """Poll for Docker test result.
        
        Checks the result marker file periodically until the test completes
        or timeout is reached. Timeout is POLL_MAX_COUNT * POLL_INTERVAL_MS.
        """
        if not self._test_folder or not self._status_callback or not self._completion_callback:
            return
            
        marker_file = os.path.join(self._test_folder, TEST_RESULT_FILE)
        self._poll_count += 1
        
        if os.path.exists(marker_file):
            # Test completed - read result
            try:
                with open(marker_file, "r", encoding="utf-8") as f:
                    result = f.read().strip()
            except (IOError, OSError) as e:
                logger.error(f"Failed to read test result file: {e}")
                self._status_callback("✗ Could not read test result", "#f44336")
                self._show_setup_help()
                self._completion_callback(False)
                self._cleanup_test_folder()
                return
                
            if result == "success":
                self._status_callback(
                    "✓ Docker test passed! PixelArch image pulled and container executed successfully.",
                    "#4caf50"
                )
                self._completion_callback(True)
            else:
                self._status_callback(
                    "✗ Docker test failed. Check terminal output for details.",
                    "#f44336"
                )
                self._show_setup_help()
                self._completion_callback(False)
            
            self._cleanup_test_folder()
            
        elif self._poll_count >= POLL_MAX_COUNT:
            # Timeout reached
            timeout_seconds = (POLL_MAX_COUNT * POLL_INTERVAL_MS) // 1000
            self._status_callback(
                f"✗ Docker test timeout ({timeout_seconds}s)",
                "#f44336"
            )
            self._show_setup_help()
            self._completion_callback(False)
            self._cleanup_test_folder()
        else:
            # Continue polling
            QTimer.singleShot(POLL_INTERVAL_MS, self._poll_result)

    def _show_setup_help(self) -> None:
        """Show a message box with Docker setup help."""
        QMessageBox.information(
            self._parent,
            "Docker Setup Help",
            f"Docker setup instructions are available at:\n\n"
            f"{DOCKER_SETUP_URL}\n\n"
            "Common issues:\n"
            "• Docker daemon not running\n"
            "• Docker socket permissions\n"
            "• Docker CLI not installed"
        )

    def _cleanup_test_folder(self) -> None:
        """Clean up the Docker test folder.
        
        Attempts to remove the temporary test folder. Logs errors but does not
        raise exceptions to avoid disrupting the UI flow.
        """
        if self._test_folder and os.path.exists(self._test_folder):
            try:
                shutil.rmtree(self._test_folder)
                logger.debug(f"Cleaned up Docker test folder: {self._test_folder}")
            except (OSError, PermissionError) as e:
                logger.warning(f"Failed to clean up Docker test folder {self._test_folder}: {e}")
            finally:
                self._test_folder = None

    def cancel(self) -> None:
        """Cancel ongoing validation and cleanup resources."""
        self._cleanup_test_folder()
        self._status_callback = None
        self._completion_callback = None
