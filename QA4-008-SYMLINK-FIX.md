# QA4-008 Symlink Security Vulnerability Fix

## Executive Summary

**CRITICAL SECURITY FIX**: Fixed a symlink bypass vulnerability in workspace validation that could allow mounting of sensitive directories (home, root, system) via symbolic links.

## Vulnerability Details

### The Problem
The original code used `os.path.abspath()` which:
- ❌ Does NOT resolve symbolic links
- ❌ Only normalizes the path string
- ❌ Allows attackers to bypass security checks using symlinks

Docker, however:
- ✅ DOES follow symbolic links when mounting
- ✅ Mounts the actual target directory, not the symlink

This mismatch created a security bypass where:
1. Security check sees: `/tmp/link_to_home` → Passes (not home)
2. Docker mounts: `/home/user` → Security breach!

### Real-World Attack Scenario
```bash
# Attacker creates symlink to home
ln -s $HOME /tmp/innocent_looking_folder

# Attacker passes workspace through our tool
# Security check with abspath() sees /tmp/innocent_looking_folder (safe)
# Docker follows symlink and mounts $HOME (security breach!)
```

## The Fix

### Changes Made
Replaced `os.path.abspath()` with `os.path.realpath()` in 4 locations:

**File: `agents_runner/docker/utils.py`**

1. **Line 41** - `_is_system_directory()` function
   ```python
   - path_abs = os.path.abspath(path)
   + path_abs = os.path.realpath(path)
   ```

2. **Line 76** - `_is_safe_mount_root()` function
   ```python
   - path = os.path.abspath(path)
   + path = os.path.realpath(path)
   ```

3. **Line 77** - `_is_safe_mount_root()` function
   ```python
   - original_workdir = os.path.abspath(original_workdir)
   + original_workdir = os.path.realpath(original_workdir)
   ```

4. **Line 131** - `_resolve_workspace_mount()` function
   ```python
   - host_workdir = os.path.abspath(os.path.expanduser(...))
   + host_workdir = os.path.realpath(os.path.expanduser(...))
   ```

### Additional Security Enhancement
Enhanced `_resolve_workspace_mount()` to ALWAYS validate mount points, even when `mount_root == host_workdir`. Previously, this case skipped validation entirely.

```python
# Added validation block at line 180-195
else:
    # Even when mount_root == host_workdir, we must validate it's not home/root/system
    home = os.path.expanduser("~")
    if mount_root == home:
        raise ValueError("Refusing to mount home directory...")
    elif mount_root == "/":
        raise ValueError("Refusing to mount root filesystem...")
    elif _is_system_directory(mount_root):
        raise ValueError("Refusing to mount system directory...")
```

## Why `realpath()` is Correct

| Function | Behavior | Example |
|----------|----------|---------|
| `os.path.abspath()` | Normalizes path, keeps symlinks | `/tmp/link` → `/tmp/link` |
| `os.path.realpath()` | Resolves ALL symlinks | `/tmp/link` → `/home/user` |

**Key Benefits:**
- ✅ Resolves symbolic links completely
- ✅ Resolves symlink chains (link1→link2→target)
- ✅ Works with relative symlinks
- ✅ Matches Docker's actual mount behavior
- ✅ Prevents security bypass

## Test Coverage

Created comprehensive test suite: `test_symlink_security.py`

### Tests Verify:
1. ✅ Direct symlink to home is rejected
2. ✅ Symlink with parent traversal to home is rejected
3. ✅ Symlink to root (/) is rejected
4. ✅ Symlink to system directories (/etc) is rejected
5. ✅ Symlink chains (link1→link2→home) are rejected
6. ✅ Relative symlinks to home are rejected
7. ✅ Safe symlinks within projects still work
8. ✅ Demonstrates abspath vs realpath difference

### Test Results
```
17 passed in 0.07s
```

All tests pass, including:
- 9 new symlink security tests
- 8 existing workspace security tests

## Security Impact

### Before Fix (VULNERABLE)
```python
# Attacker creates symlink
os.symlink("/home/user", "/tmp/backdoor")

# Security check (BYPASSED)
mount_path = os.path.abspath("/tmp/backdoor")
# Returns: "/tmp/backdoor" → Passes security check

# Docker mount (SECURITY BREACH)
# Docker follows symlink → Mounts /home/user
```

### After Fix (SECURE)
```python
# Attacker creates symlink
os.symlink("/home/user", "/tmp/backdoor")

# Security check (CATCHES IT)
mount_path = os.path.realpath("/tmp/backdoor")
# Returns: "/home/user" → Fails security check → ValueError raised

# Attack prevented!
```

## Files Changed

1. `agents_runner/docker/utils.py` - Core security fix (4 locations + validation enhancement)
2. `test_symlink_security.py` - NEW comprehensive test suite (9 tests)
3. `QA4-008-SYMLINK-FIX.md` - This documentation

## Verification Steps

1. Run tests:
   ```bash
   pytest test_symlink_security.py test_workspace_security.py -v
   ```

2. Manual verification:
   ```bash
   # Create symlink to home
   ln -s $HOME /tmp/test_link
   
   # Try to use it (should be rejected)
   # The tool will now correctly identify and reject this
   ```

## Commit Message
```
[SECURITY] qa4-008: Fix symlink bypass vulnerability in workspace validation

Critical fix: Replace os.path.abspath() with os.path.realpath() to properly
resolve symbolic links and prevent attackers from bypassing security checks.

Without this fix, symlinks to home/root/system directories could bypass all
security validation because abspath() doesn't resolve symlinks, but Docker
does follow them when mounting.

Changes:
- Replace abspath() with realpath() in 4 locations
- Add validation for mount_root == host_workdir case
- Add comprehensive symlink security test suite

Impact: Prevents exposure of sensitive directories via symlink attacks.
```

## Security Advisory

**Severity:** CRITICAL  
**CVE:** qa4-008-symlink-bypass  
**Component:** Docker workspace mount validation  
**Affected:** All versions using os.path.abspath()  
**Fixed in:** This commit  

**Recommendation:** Deploy immediately to all environments.
