#!/usr/bin/env python3
"""
Comprehensive security tests for qa4-008: Workspace mount validation
"""

import os
import tempfile
import shutil
from pathlib import Path

# Import the functions we're testing
from agents_runner.docker.utils import (
    _resolve_workspace_mount,
    _is_safe_mount_root,
    _is_system_directory,
)


def test_system_directory_detection():
    """Test that system directories are correctly identified."""
    print("TEST: System directory detection")
    print("-" * 60)
    
    test_cases = [
        ("/etc", True, "exact match /etc"),
        ("/etc/nginx", True, "subdirectory of /etc"),
        ("/var", True, "exact match /var"),
        ("/var/log/nginx", True, "deep subdirectory of /var"),
        ("/usr", True, "exact match /usr"),
        ("/usr/local/bin", True, "subdirectory of /usr"),
        ("/opt", True, "exact match /opt"),
        ("/srv", True, "exact match /srv"),
        ("/root", True, "exact match /root"),
        ("/boot", True, "exact match /boot"),
        ("/sys", True, "exact match /sys"),
        ("/proc", True, "exact match /proc"),
        ("/home/user", False, "not a system dir"),
        ("/tmp", False, "not a system dir"),
        ("/custom", False, "not a system dir"),
    ]
    
    passed = 0
    failed = 0
    
    for path, expected, description in test_cases:
        result = _is_system_directory(path)
        if result == expected:
            print(f"  ✓ {description}: {path} -> {result}")
            passed += 1
        else:
            print(f"  ✗ {description}: {path} -> {result} (expected {expected})")
            failed += 1
    
    print(f"\nResult: {passed} passed, {failed} failed\n")
    return failed == 0


def test_home_directory_boundary():
    """Test that home directory cannot be mounted."""
    print("TEST: Home directory boundary protection")
    print("-" * 60)
    
    home = os.path.expanduser("~")
    workdir = os.path.join(home, "projects", "myapp")
    
    result = _is_safe_mount_root(home, workdir)
    if not result:
        print(f"  ✓ Home directory {home} correctly blocked")
        print(f"    (requested workdir: {workdir})")
        print()
        return True
    else:
        print(f"  ✗ SECURITY FAILURE: Home directory {home} was allowed!")
        print()
        return False


def test_root_filesystem_boundary():
    """Test that root filesystem cannot be mounted."""
    print("TEST: Root filesystem boundary protection")
    print("-" * 60)
    
    workdir = "/opt/app/backend/src"
    
    result = _is_safe_mount_root("/", workdir)
    if not result:
        print(f"  ✓ Root filesystem (/) correctly blocked")
        print(f"    (requested workdir: {workdir})")
        print()
        return True
    else:
        print(f"  ✗ SECURITY FAILURE: Root filesystem (/) was allowed!")
        print()
        return False


def test_depth_limit():
    """Test that traversal depth limit is enforced."""
    print("TEST: Traversal depth limit (max 3 levels)")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a structure that exceeds max depth
        deep_path = os.path.join(tmpdir, "a", "b", "c", "d")
        os.makedirs(deep_path, exist_ok=True)
        
        # Test depth of 3 (should pass)
        workdir_3 = os.path.join(tmpdir, "a", "b", "c")
        os.makedirs(workdir_3, exist_ok=True)
        result_3 = _is_safe_mount_root(tmpdir, workdir_3, max_depth=3)
        
        # Test depth of 4 (should fail)
        workdir_4 = os.path.join(tmpdir, "a", "b", "c", "d")
        result_4 = _is_safe_mount_root(tmpdir, workdir_4, max_depth=3)
        
        passed = 0
        failed = 0
        
        if result_3:
            print(f"  ✓ Depth 3 allowed (within limit)")
            passed += 1
        else:
            print(f"  ✗ Depth 3 rejected (should be allowed)")
            failed += 1
        
        if not result_4:
            print(f"  ✓ Depth 4 blocked (exceeds limit)")
            passed += 1
        else:
            print(f"  ✗ SECURITY FAILURE: Depth 4 allowed (should be blocked)")
            failed += 1
        
        print(f"\nResult: {passed} passed, {failed} failed\n")
        return failed == 0


def test_safe_nested_project():
    """Test that normal nested project structure works correctly."""
    print("TEST: Safe nested project (normal use case)")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create project structure
        project_dir = os.path.join(tmpdir, "myproject")
        src_dir = os.path.join(project_dir, "src")
        os.makedirs(src_dir)
        
        # Add .git marker
        git_dir = os.path.join(project_dir, ".git")
        os.makedirs(git_dir)
        
        try:
            mount_root, container_dir = _resolve_workspace_mount(
                src_dir, container_mount="/workspace"
            )
            
            expected_mount = project_dir
            if mount_root == expected_mount:
                print(f"  ✓ Correct mount root: {mount_root}")
                print(f"    User requested: {src_dir}")
                print(f"    Container workdir: {container_dir}")
                print()
                return True
            else:
                print(f"  ✗ Incorrect mount root: {mount_root}")
                print(f"    Expected: {expected_mount}")
                print()
                return False
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            print()
            return False


def test_parent_mount_blocked():
    """Test that unsafe parent mounts are blocked."""
    print("TEST: Parent mount boundary violation")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Simulate home directory scenario
        fake_home = os.path.join(tmpdir, "home", "user")
        os.makedirs(fake_home)
        
        # Create .git in "home"
        git_dir = os.path.join(fake_home, ".git")
        os.makedirs(git_dir)
        
        # Create nested project without marker
        project_dir = os.path.join(fake_home, "projects", "app", "src", "subdir")
        os.makedirs(project_dir)
        
        # Temporarily override home for this test
        original_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = fake_home
            
            try:
                mount_root, _ = _resolve_workspace_mount(
                    project_dir, container_mount="/workspace"
                )
                
                # Check if it tried to mount the fake home
                if mount_root == fake_home:
                    print(f"  ✗ SECURITY FAILURE: Mounted home directory!")
                    print(f"    Mount root: {mount_root}")
                    print(f"    Requested: {project_dir}")
                    print()
                    return False
                else:
                    print(f"  ✓ Did not mount home directory")
                    print(f"    Mount root: {mount_root}")
                    print()
                    return True
                    
            except ValueError as e:
                print(f"  ✓ Parent mount correctly blocked with error:")
                print(f"    {str(e).split(chr(10))[0]}")
                print()
                return True
                
        finally:
            if original_home:
                os.environ["HOME"] = original_home
            else:
                os.environ.pop("HOME", None)


def test_excessive_depth_blocked():
    """Test that traversing too many levels up is blocked."""
    print("TEST: Excessive depth traversal blocked")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create very deep structure
        levels = ["a", "b", "c", "d", "e"]
        deep_path = tmpdir
        for level in levels:
            deep_path = os.path.join(deep_path, level)
        os.makedirs(deep_path)
        
        # Add .git at the top
        git_dir = os.path.join(tmpdir, ".git")
        os.makedirs(git_dir)
        
        try:
            mount_root, _ = _resolve_workspace_mount(
                deep_path, container_mount="/workspace"
            )
            
            # Should fail or mount deep_path itself (not tmpdir)
            if mount_root == tmpdir:
                print(f"  ✗ SECURITY FAILURE: Excessive traversal allowed!")
                print(f"    Mounted: {mount_root}")
                print(f"    From: {deep_path}")
                print()
                return False
            else:
                print(f"  ✓ Excessive traversal prevented")
                print(f"    Mounted: {mount_root}")
                print(f"    Requested: {deep_path}")
                print()
                return True
                
        except ValueError as e:
            print(f"  ✓ Excessive traversal blocked with error:")
            print(f"    {str(e).split(chr(10))[0]}")
            print()
            return True


def test_no_marker_fallback():
    """Test that when no marker is found, the workdir itself is used."""
    print("TEST: No marker fallback (returns workdir)")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory without any markers
        workdir = os.path.join(tmpdir, "project", "src")
        os.makedirs(workdir)
        
        try:
            mount_root, container_dir = _resolve_workspace_mount(
                workdir, container_mount="/workspace"
            )
            
            if mount_root == workdir:
                print(f"  ✓ Correctly returned workdir when no marker found")
                print(f"    Mount root: {mount_root}")
                print(f"    Container dir: {container_dir}")
                print()
                return True
            else:
                print(f"  ✗ Unexpected mount root: {mount_root}")
                print(f"    Expected: {workdir}")
                print()
                return False
                
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            print()
            return False


def main():
    """Run all security tests."""
    print("=" * 80)
    print("QA4-008 SECURITY TEST SUITE")
    print("Testing workspace mount boundary validation")
    print("=" * 80)
    print()
    
    tests = [
        ("System directory detection", test_system_directory_detection),
        ("Home directory boundary", test_home_directory_boundary),
        ("Root filesystem boundary", test_root_filesystem_boundary),
        ("Traversal depth limit", test_depth_limit),
        ("Safe nested project", test_safe_nested_project),
        ("Parent mount blocked", test_parent_mount_blocked),
        ("Excessive depth blocked", test_excessive_depth_blocked),
        ("No marker fallback", test_no_marker_fallback),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"  ✗ Test '{name}' crashed: {e}")
            print()
            results.append((name, False))
    
    # Print summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    failed_count = len(results) - passed_count
    
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {status}: {name}")
    
    print()
    print(f"Total: {passed_count}/{len(results)} tests passed")
    
    if failed_count > 0:
        print()
        print(f"⚠️  {failed_count} test(s) failed!")
        return 1
    else:
        print()
        print("✅ All security tests passed!")
        return 0


if __name__ == "__main__":
    exit(main())
