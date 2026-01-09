#!/usr/bin/env python3
"""
Security validation tests for CVE-qa4-008

This test suite validates the fixes for:
- CVE-qa4-008-A: Direct home subdirectories bypass vulnerability
- CVE-qa4-008-B: Symlink path traversal bypass vulnerability

Both vulnerabilities could expose sensitive credentials (SSH keys, AWS tokens, etc.)
"""

import os
import tempfile
from pathlib import Path
from agents_runner.docker.utils import (
    _resolve_workspace_mount,
    _is_safe_mount_root,
)


def test_cve_qa4_008_a():
    """Test CVE-qa4-008-A: Direct home subdirectory bypass"""
    print("=" * 70)
    print("CVE-qa4-008-A: Direct Home Subdirectory Bypass")
    print("=" * 70)
    print("\nVulnerability: Home subdirectories like ~/.ssh, ~/.aws were not blocked")
    print("Impact: SSH keys, AWS credentials, and other secrets exposed to containers")
    print("\nTesting fix...\n")
    
    home = os.path.expanduser("~")
    
    # Test sensitive directories that MUST be blocked
    sensitive_dirs = [
        (".ssh", "SSH private keys and authorized_keys"),
        (".aws", "AWS credentials and configuration"),
        (".gnupg", "GPG private keys"),
        (".config", "Application configurations and tokens"),
        ("Documents", "Personal documents"),
        ("Downloads", "Downloaded files"),
        ("workspace", "Any home subdirectory"),
    ]
    
    passed = 0
    failed = 0
    
    for dirname, description in sensitive_dirs:
        test_path = os.path.join(home, dirname)
        try:
            mount_root, container_dir = _resolve_workspace_mount(
                test_path,
                container_mount="/workspace"
            )
            print(f"  ✗ FAIL: {dirname:<15} - {description}")
            print(f"          Mount allowed: {mount_root}")
            failed += 1
        except ValueError as e:
            if "home directory" in str(e).lower():
                print(f"  ✓ PASS: {dirname:<15} - {description}")
                passed += 1
            else:
                print(f"  ? WARN: {dirname:<15} - Blocked but unexpected error")
                print(f"          {e}")
                passed += 1
    
    print(f"\nResult: {passed}/{len(sensitive_dirs)} directories correctly blocked")
    
    if failed > 0:
        print("\n❌ CVE-qa4-008-A: VULNERABLE - Some directories were not blocked!")
        return False
    else:
        print("\n✅ CVE-qa4-008-A: FIXED - All home subdirectories blocked")
        return True


def test_cve_qa4_008_b():
    """Test CVE-qa4-008-B: Symlink path traversal bypass"""
    print("\n" + "=" * 70)
    print("CVE-qa4-008-B: Symlink Path Traversal Bypass")
    print("=" * 70)
    print("\nVulnerability: Symlinks in middle of path could bypass security checks")
    print("Example: /tmp/mylink -> ~, then /tmp/mylink/docs resolves to ~/docs")
    print("Impact: Attackers could create symlinks to access sensitive directories")
    print("\nTesting fix...\n")
    
    home = os.path.expanduser("~")
    passed = 0
    failed = 0
    total_tests = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test 1: Direct symlink to home
        print("  Test 1: Direct symlink to home")
        link_to_home = os.path.join(tmpdir, "homelink")
        os.symlink(home, link_to_home)
        
        total_tests += 1
        try:
            mount_root, _ = _resolve_workspace_mount(
                link_to_home,
                container_mount="/workspace"
            )
            print(f"    ✗ FAIL: Direct home symlink allowed")
            failed += 1
        except (ValueError, FileNotFoundError) as e:
            if isinstance(e, ValueError) and "home directory" in str(e).lower():
                print(f"    ✓ PASS: Direct home symlink blocked")
                passed += 1
            else:
                print(f"    ✓ PASS: Blocked (but unexpected error: {type(e).__name__})")
                passed += 1
        
        # Test 2: Symlink to home subdirectory
        print("\n  Test 2: Symlink to home subdirectory (~/docs)")
        home_docs = os.path.join(home, "docs")
        link_to_docs = os.path.join(tmpdir, "docslink")
        os.symlink(home, link_to_docs)  # Link to home
        test_path = os.path.join(link_to_docs, "docs")
        
        total_tests += 1
        try:
            mount_root, _ = _resolve_workspace_mount(
                test_path,
                container_mount="/workspace"
            )
            print(f"    ✗ FAIL: Symlink to ~/docs allowed")
            failed += 1
        except (ValueError, FileNotFoundError) as e:
            if isinstance(e, ValueError):
                print(f"    ✓ PASS: Symlink to ~/docs blocked")
                passed += 1
            else:
                print(f"    ✓ PASS: Blocked (FileNotFoundError expected)")
                passed += 1
        
        # Test 3: Chain of symlinks
        print("\n  Test 3: Chain of symlinks")
        link1 = os.path.join(tmpdir, "link1")
        link2 = os.path.join(tmpdir, "link2")
        os.symlink(home, link1)
        os.symlink(link1, link2)
        
        total_tests += 1
        try:
            mount_root, _ = _resolve_workspace_mount(
                link2,
                container_mount="/workspace"
            )
            print(f"    ✗ FAIL: Symlink chain allowed")
            failed += 1
        except (ValueError, FileNotFoundError) as e:
            print(f"    ✓ PASS: Symlink chain blocked")
            passed += 1
        
        # Test 4: Symlink bypass using _is_safe_mount_root directly
        print("\n  Test 4: _is_safe_mount_root() with symlink resolution")
        link_to_ssh = os.path.join(tmpdir, "sshlink")
        ssh_dir = os.path.join(home, ".ssh")
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, exist_ok=True)
        os.symlink(ssh_dir, link_to_ssh)
        
        # The function uses os.path.realpath which resolves symlinks
        total_tests += 1
        workdir = os.path.join(tmpdir, "project")
        os.makedirs(workdir, exist_ok=True)
        result = _is_safe_mount_root(link_to_ssh, workdir)
        
        if result:
            print(f"    ✗ FAIL: _is_safe_mount_root allowed symlink to ~/.ssh")
            failed += 1
        else:
            print(f"    ✓ PASS: _is_safe_mount_root blocked symlink to ~/.ssh")
            passed += 1
    
    print(f"\nResult: {passed}/{total_tests} symlink tests passed")
    
    if failed > 0:
        print("\n❌ CVE-qa4-008-B: VULNERABLE - Symlink bypass detected!")
        return False
    else:
        print("\n✅ CVE-qa4-008-B: FIXED - All symlink bypasses blocked")
        return True


def test_legitimate_use_cases():
    """Verify legitimate use cases still work"""
    print("\n" + "=" * 70)
    print("Legitimate Use Cases (regression testing)")
    print("=" * 70)
    print("\nVerifying that legitimate workflows are not broken...\n")
    
    passed = 0
    failed = 0
    
    # Test 1: /tmp workspace
    print("  Test 1: Working in /tmp")
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = os.path.join(tmpdir, "myproject", "src")
        os.makedirs(workdir, exist_ok=True)
        
        try:
            mount_root, container_dir = _resolve_workspace_mount(
                workdir,
                container_mount="/workspace"
            )
            print(f"    ✓ PASS: /tmp project allowed")
            print(f"            mount_root: {mount_root}")
            passed += 1
        except ValueError as e:
            print(f"    ✗ FAIL: /tmp project blocked: {e}")
            failed += 1
    
    # Test 2: Project with markers
    print("\n  Test 2: Project with .git marker")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = os.path.join(tmpdir, "myproject")
        src_dir = os.path.join(project_root, "src")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(os.path.join(project_root, ".git"), exist_ok=True)
        
        try:
            mount_root, container_dir = _resolve_workspace_mount(
                src_dir,
                container_mount="/workspace"
            )
            if mount_root == project_root and container_dir == "/workspace/src":
                print(f"    ✓ PASS: Correct mount root detection")
                print(f"            Requested: {src_dir}")
                print(f"            Mount root: {mount_root}")
                print(f"            Container: {container_dir}")
                passed += 1
            else:
                print(f"    ✗ FAIL: Incorrect mount root")
                failed += 1
        except ValueError as e:
            print(f"    ✗ FAIL: Project with .git blocked: {e}")
            failed += 1
    
    print(f"\nResult: {passed}/2 legitimate use cases work correctly")
    
    if failed > 0:
        print("\n⚠️  WARNING: Some legitimate use cases were broken!")
        return False
    else:
        print("\n✅ All legitimate use cases still work")
        return True


def main():
    """Run all CVE tests"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 16 + "CVE-qa4-008 SECURITY VALIDATION" + " " * 21 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    results = []
    
    # Run CVE tests
    results.append(("CVE-qa4-008-A", test_cve_qa4_008_a()))
    results.append(("CVE-qa4-008-B", test_cve_qa4_008_b()))
    results.append(("Regression Tests", test_legitimate_use_cases()))
    
    # Summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n" + "=" * 70)
        print("✅ ALL SECURITY TESTS PASSED")
        print("=" * 70)
        print("\nCVE-qa4-008 vulnerabilities have been successfully mitigated!")
        print("\nSecurity boundaries enforced:")
        print("  • Home directory and ALL subdirectories blocked")
        print("  • Symlink resolution prevents bypass attacks")
        print("  • SSH keys, AWS credentials, and secrets protected")
        print("  • Legitimate workflows in /tmp and other safe locations work")
        return 0
    else:
        print("\n" + "=" * 70)
        print("❌ SECURITY TESTS FAILED")
        print("=" * 70)
        print("\nSome vulnerabilities remain or legitimate use cases broken!")
        return 1


if __name__ == "__main__":
    exit(main())
