#!/usr/bin/env python3
"""
Bulk import Lucide SVG icons using git sparse-checkout.
Prioritizes essential and common UI icons, then fills to ~800 total.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Set

# Priority lists as specified
ESSENTIAL_ICONS = [
    "home", "house", "folder", "folder-plus", "plus", "list", "layout-list",
    "pause", "play", "square", "stop-circle", "rotate-cw", "refresh-cw",
    "rotate-ccw", "trash", "trash-2"
]

COMMON_UI_ICONS = [
    "copy", "external-link", "search", "settings", "check", "x", "info",
    "alert-circle", "github", "arrow-left", "arrow-right", "download",
    "upload", "edit", "save", "file", "file-text", "help-circle", "menu",
    "more-horizontal", "more-vertical"
]

TARGET_TOTAL = 800
LUCIDE_REPO = "https://github.com/lucide-icons/lucide.git"
DEST_DIR = Path("agents_runner/assets/icons/lucide")


def run_command(cmd: List[str], cwd: str = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def clone_with_sparse_checkout(clone_dir: Path) -> None:
    """Clone lucide repo with sparse-checkout for icons directory."""
    print(f"\n📦 Cloning Lucide repository with sparse-checkout...")
    
    # Initialize empty repo
    run_command(["git", "init"], cwd=str(clone_dir))
    
    # Configure sparse-checkout
    run_command(["git", "config", "core.sparseCheckout", "true"], cwd=str(clone_dir))
    
    # Set sparse-checkout patterns
    sparse_file = clone_dir / ".git" / "info" / "sparse-checkout"
    sparse_file.parent.mkdir(parents=True, exist_ok=True)
    sparse_file.write_text("icons/\n")
    
    # Add remote and fetch
    run_command(["git", "remote", "add", "origin", LUCIDE_REPO], cwd=str(clone_dir))
    run_command(["git", "fetch", "--depth=1", "origin", "main"], cwd=str(clone_dir))
    
    # Checkout
    run_command(["git", "checkout", "main"], cwd=str(clone_dir))
    
    print("✅ Sparse checkout completed")


def get_available_icons(icons_dir: Path) -> List[str]:
    """Get list of available icon names (without .svg extension)."""
    if not icons_dir.exists():
        return []
    
    icons = []
    for svg_file in icons_dir.glob("*.svg"):
        icons.append(svg_file.stem)
    
    return sorted(icons)


def validate_svg_file(file_path: Path) -> bool:
    """Validate that a file is a non-empty SVG."""
    if file_path.stat().st_size == 0:
        print(f"  ❌ {file_path.name}: 0 bytes")
        return False
    
    try:
        content = file_path.read_text(encoding='utf-8')
        if '<svg' not in content:
            print(f"  ❌ {file_path.name}: No <svg tag found")
            return False
    except Exception as e:
        print(f"  ❌ {file_path.name}: Read error - {e}")
        return False
    
    return True


def copy_icons(src_icons_dir: Path, dest_dir: Path, icon_names: List[str]) -> tuple[int, int, List[str]]:
    """
    Copy specified icons from source to destination.
    Returns (success_count, failure_count, failed_icons).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    failure_count = 0
    failed_icons = []
    
    for icon_name in icon_names:
        src_file = src_icons_dir / f"{icon_name}.svg"
        dest_file = dest_dir / f"{icon_name}.svg"
        
        if not src_file.exists():
            print(f"  ⚠️  {icon_name}.svg: Not found in source")
            failure_count += 1
            failed_icons.append(icon_name)
            continue
        
        # Copy file
        shutil.copy2(src_file, dest_file)
        
        # Validate
        if not validate_svg_file(dest_file):
            dest_file.unlink()  # Remove invalid file
            failure_count += 1
            failed_icons.append(icon_name)
        else:
            success_count += 1
    
    return success_count, failure_count, failed_icons


def main():
    """Main import process."""
    print("🎨 Lucide Icon Bulk Import")
    print("=" * 60)
    
    # Create temporary directory for clone
    temp_dir = Path("/tmp/lucide_clone")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    
    try:
        # Clone with sparse-checkout
        clone_with_sparse_checkout(temp_dir)
        
        # Find icons directory
        src_icons_dir = temp_dir / "icons"
        if not src_icons_dir.exists():
            print(f"❌ ERROR: Icons directory not found at {src_icons_dir}")
            sys.exit(1)
        
        # Get all available icons
        available_icons = get_available_icons(src_icons_dir)
        print(f"\n📊 Found {len(available_icons)} icons in upstream repository")
        
        # Build prioritized list
        prioritized_icons = []
        
        # 1. Essential icons (must have)
        print(f"\n1️⃣  Adding {len(ESSENTIAL_ICONS)} essential icons...")
        for icon in ESSENTIAL_ICONS:
            if icon in available_icons:
                prioritized_icons.append(icon)
            else:
                print(f"  ⚠️  Essential icon '{icon}' not found in upstream!")
        
        # 2. Common UI icons
        print(f"\n2️⃣  Adding {len(COMMON_UI_ICONS)} common UI icons...")
        for icon in COMMON_UI_ICONS:
            if icon in available_icons and icon not in prioritized_icons:
                prioritized_icons.append(icon)
        
        # 3. Fill remaining slots up to TARGET_TOTAL
        remaining_slots = TARGET_TOTAL - len(prioritized_icons)
        print(f"\n3️⃣  Filling {remaining_slots} remaining slots...")
        
        for icon in available_icons:
            if icon not in prioritized_icons:
                prioritized_icons.append(icon)
                if len(prioritized_icons) >= TARGET_TOTAL:
                    break
        
        print(f"\n📋 Selected {len(prioritized_icons)} icons to import")
        
        # Copy icons
        print(f"\n📂 Copying icons to {DEST_DIR}...")
        success, failures, failed_list = copy_icons(src_icons_dir, DEST_DIR, prioritized_icons)
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 IMPORT SUMMARY")
        print("=" * 60)
        print(f"Requested:  {len(prioritized_icons)}")
        print(f"Succeeded:  {success}")
        print(f"Failed:     {failures}")
        
        if failed_list:
            print(f"\n❌ Failed icons ({len(failed_list)}):")
            for icon in failed_list[:20]:  # Show first 20
                print(f"  - {icon}")
            if len(failed_list) > 20:
                print(f"  ... and {len(failed_list) - 20} more")
        
        # Validate final state
        print(f"\n🔍 Final validation...")
        final_files = list(DEST_DIR.glob("*.svg"))
        print(f"Total SVG files in destination: {len(final_files)}")
        
        # Check for any 0-byte files
        zero_byte_files = [f for f in final_files if f.stat().st_size == 0]
        if zero_byte_files:
            print(f"❌ ERROR: Found {len(zero_byte_files)} zero-byte files!")
            for f in zero_byte_files:
                print(f"  - {f.name}")
            sys.exit(1)
        
        print("✅ All files validated successfully")
        
        if failures > 0:
            print(f"\n⚠️  Import completed with {failures} failures")
            sys.exit(1)
        else:
            print("\n✅ Import completed successfully!")
            sys.exit(0)
            
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up temporary directory...")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
