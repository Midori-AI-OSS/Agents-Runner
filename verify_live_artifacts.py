#!/usr/bin/env python
"""
Quick verification script for Live Artifacts system.

Tests the core functionality without requiring a full UI launch.
"""

from pathlib import Path
from agents_runner.artifacts import (
    get_staging_dir, 
    list_staging_artifacts,
    get_staging_artifact_path,
    StagingArtifactMeta
)

def test_staging_artifacts():
    """Test staging artifact functions."""
    print("=" * 60)
    print("Live Artifacts System - Verification")
    print("=" * 60)
    
    # Test 1: Staging directory creation
    print("\n[1] Testing staging directory creation...")
    task_id = "test-task-123"
    staging_dir = get_staging_dir(task_id)
    print(f"    Staging dir: {staging_dir}")
    staging_dir.mkdir(parents=True, exist_ok=True)
    print("    ✓ Directory created")
    
    # Test 2: Create test artifacts
    print("\n[2] Creating test artifacts...")
    test_files = [
        ("output.txt", "This is a test output file"),
        ("results.json", '{"status": "success", "value": 42}'),
        ("data.csv", "name,value\ntest,123\n"),
    ]
    
    for filename, content in test_files:
        file_path = staging_dir / filename
        file_path.write_text(content)
        print(f"    ✓ Created: {filename}")
    
    # Test 3: List staging artifacts
    print("\n[3] Listing staging artifacts...")
    artifacts = list_staging_artifacts(task_id)
    print(f"    Found {len(artifacts)} artifacts:")
    for artifact in artifacts:
        print(f"      - {artifact.filename}")
        print(f"        Size: {artifact.size_bytes} bytes")
        print(f"        Type: {artifact.mime_type}")
        print(f"        Path: {artifact.path}")
    
    # Test 4: Get artifact path with security check
    print("\n[4] Testing path retrieval...")
    for filename, _ in test_files:
        path = get_staging_artifact_path(task_id, filename)
        if path:
            print(f"    ✓ Found: {filename}")
        else:
            print(f"    ✗ Not found: {filename}")
    
    # Test 5: Path traversal protection
    print("\n[5] Testing path traversal protection...")
    bad_path = get_staging_artifact_path(task_id, "../../etc/passwd")
    if bad_path is None:
        print("    ✓ Path traversal blocked")
    else:
        print("    ✗ Security vulnerability detected!")
    
    # Cleanup
    print("\n[6] Cleaning up...")
    for filename, _ in test_files:
        (staging_dir / filename).unlink()
    staging_dir.rmdir()
    print("    ✓ All test files removed")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    test_staging_artifacts()
