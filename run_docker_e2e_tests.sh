#!/bin/bash
# Helper script to run Docker E2E tests
# These tests require Docker socket access

set -e

echo "Checking Docker access..."
if docker ps > /dev/null 2>&1; then
    echo "✓ Docker is accessible"
    echo ""
    echo "Running E2E tests..."
    uv run pytest agents_runner/tests/test_docker_e2e.py -v "$@"
else
    echo "✗ Docker is not accessible"
    echo ""
    echo "To run these tests, you need Docker access. Options:"
    echo "  1. Add your user to the docker group:"
    echo "     sudo usermod -aG docker \$USER"
    echo "     Then log out and back in"
    echo ""
    echo "  2. Run with sudo (not recommended):"
    echo "     sudo ./run_docker_e2e_tests.sh"
    exit 1
fi
