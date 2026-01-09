#!/usr/bin/env python3
"""
Test suite for symlink security vulnerability fix (qa4-008).

This test verifies that symbolic links cannot be used to bypass security
checks and mount sensitive directories like the home directory.
"""

import os
import tempfile
import shutil
from pathlib import Path
import pytest

from agents_runner.docker.utils import _resolve_workspace_mount, _is_safe_mount_root


class TestSymlinkSecurityFix:
    """Test that symlinks don't bypass security checks."""
    
    def test_symlink_to_home_is_rejected(self, tmp_path):
        """
        CRITICAL: Symlink pointing to home directory itself should be rejected.
        
        This is the main vulnerability - os.path.abspath() doesn't resolve
        symlinks, but Docker does follow them when mounting.
        """
        home = Path.home()
        
        # Create a symlink to home directory
        symlink_to_home = tmp_path / "link_to_home"
        symlink_to_home.symlink_to(home)
        
        # Try to mount home itself via symlink
        with pytest.raises(ValueError) as exc_info:
            _resolve_workspace_mount(
                str(symlink_to_home),
                container_mount="/workspace"
            )
        
        assert "home directory" in str(exc_info.value).lower()
        print(f"✅ Symlink to home correctly rejected: {exc_info.value}")
    
    def test_symlink_to_home_with_marker_is_rejected(self, tmp_path):
        """
        CRITICAL: Symlink to subdir that traverses UP to home with marker should be rejected.
        
        If a project marker (.git) exists at home level, traversal could mount home.
        """
        home = Path.home()
        
        # Create a symlink to home directory
        symlink_to_home = tmp_path / "link_to_home"
        symlink_to_home.symlink_to(home)
        
        # Create a project subdirectory
        fake_project = symlink_to_home / "project"
        fake_project.mkdir(parents=True, exist_ok=True)
        
        # Create .git marker at home level (via symlink)
        fake_git = symlink_to_home / ".git"
        fake_git.mkdir(exist_ok=True)
        
        try:
            # This should raise ValueError because traversal finds home
            with pytest.raises(ValueError) as exc_info:
                _resolve_workspace_mount(
                    str(fake_project),
                    container_mount="/workspace"
                )
            
            assert "home directory" in str(exc_info.value).lower()
            print(f"✅ Symlink with traversal to home correctly rejected: {exc_info.value}")
        finally:
            # Cleanup
            if fake_git.exists():
                fake_git.rmdir()
    
    def test_symlink_to_root_is_rejected(self, tmp_path):
        """Symlink pointing to root filesystem should be rejected."""
        # Create a symlink to root
        symlink_to_root = tmp_path / "link_to_root"
        symlink_to_root.symlink_to("/")
        
        # This should raise ValueError - mounting root itself
        with pytest.raises(ValueError) as exc_info:
            _resolve_workspace_mount(
                str(symlink_to_root),
                container_mount="/workspace"
            )
        
        assert "root filesystem" in str(exc_info.value).lower()
        print(f"✅ Symlink to root correctly rejected: {exc_info.value}")
    
    def test_symlink_to_system_dir_is_rejected(self, tmp_path):
        """Symlink pointing to system directory should be rejected."""
        # Create a symlink to /etc
        symlink_to_etc = tmp_path / "link_to_etc"
        symlink_to_etc.symlink_to("/etc")
        
        # This should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            _resolve_workspace_mount(
                str(symlink_to_etc),
                container_mount="/workspace"
            )
        
        assert "system directory" in str(exc_info.value).lower()
        print(f"✅ Symlink to system dir correctly rejected: {exc_info.value}")
    
    def test_is_safe_mount_root_with_symlink_to_home(self, tmp_path):
        """Test _is_safe_mount_root directly with symlink to home."""
        home = Path.home()
        
        # Create symlink to home
        symlink_to_home = tmp_path / "link_to_home"
        symlink_to_home.symlink_to(home)
        
        fake_workdir = symlink_to_home / "project"
        fake_workdir.mkdir(parents=True, exist_ok=True)
        
        # Should return False (unsafe) because realpath resolves to home
        result = _is_safe_mount_root(str(symlink_to_home), str(fake_workdir))
        assert result is False, "Symlink to home should be unsafe"
        print("✅ _is_safe_mount_root correctly identifies symlink to home as unsafe")
    
    def test_normal_symlinks_within_safe_paths_work(self, tmp_path):
        """Normal symlinks within safe directories should still work."""
        # Create a safe project directory
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        
        # Create a git marker to make it look like a repo
        (project_dir / ".git").mkdir()
        
        # Create a subdirectory
        subdir = project_dir / "src"
        subdir.mkdir()
        
        # Create a symlink within the project (this is safe)
        symlink_to_src = project_dir / "link_to_src"
        symlink_to_src.symlink_to(subdir)
        
        # This should work fine - symlink is within safe bounds
        mount_root, container_workdir = _resolve_workspace_mount(
            str(symlink_to_src),
            container_mount="/workspace"
        )
        
        # Should resolve to the project root
        assert Path(mount_root).resolve() == project_dir.resolve()
        print(f"✅ Safe internal symlink works: {mount_root}")
    
    def test_symlink_chain_to_home_is_rejected(self, tmp_path):
        """Chain of symlinks eventually pointing to home should be rejected."""
        home = Path.home()
        
        # Create chain: link1 -> link2 -> home
        link1 = tmp_path / "link1"
        link2 = tmp_path / "link2"
        
        link2.symlink_to(home)
        link1.symlink_to(link2)
        
        # Should be rejected - realpath() resolves entire chain
        with pytest.raises(ValueError) as exc_info:
            _resolve_workspace_mount(
                str(link1),
                container_mount="/workspace"
            )
        
        assert "home directory" in str(exc_info.value).lower()
        print(f"✅ Symlink chain to home correctly rejected: {exc_info.value}")
    
    def test_relative_symlink_to_home_is_rejected(self, tmp_path):
        """Relative symlink pointing outside to home should be rejected."""
        home = Path.home()
        
        # Create a directory structure
        safe_dir = tmp_path / "safe"
        safe_dir.mkdir()
        
        # Create relative symlink that escapes to home
        # Calculate relative path from safe_dir to home
        try:
            rel_path = os.path.relpath(home, safe_dir)
            symlink = safe_dir / "link_to_home"
            symlink.symlink_to(rel_path)
            
            # Should be rejected
            with pytest.raises(ValueError) as exc_info:
                _resolve_workspace_mount(
                    str(symlink),
                    container_mount="/workspace"
                )
            
            assert "home directory" in str(exc_info.value).lower()
            print(f"✅ Relative symlink to home correctly rejected: {exc_info.value}")
        except ValueError:
            # Different drives on Windows
            pytest.skip("Cannot create relative path (different drives)")


def test_realpath_vs_abspath_difference():
    """
    Demonstrate the difference between abspath and realpath.
    
    This test shows why realpath() is necessary for security.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        
        # Create actual directory
        real_dir = tmp_path / "real_directory"
        real_dir.mkdir()
        
        # Create symlink
        symlink = tmp_path / "symlink_to_real"
        symlink.symlink_to(real_dir)
        
        # Compare abspath vs realpath
        abspath_result = os.path.abspath(symlink)
        realpath_result = os.path.realpath(symlink)
        
        print(f"\nSymlink: {symlink}")
        print(f"Target: {real_dir}")
        print(f"os.path.abspath(): {abspath_result}")
        print(f"os.path.realpath(): {realpath_result}")
        
        # abspath keeps the symlink path
        assert str(symlink.resolve()) == realpath_result
        assert abspath_result != realpath_result or not symlink.is_symlink()
        
        print("\n✅ Demonstrated: realpath() resolves symlinks, abspath() does not")


if __name__ == "__main__":
    # Run tests with verbose output
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
