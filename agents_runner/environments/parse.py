"""Parsing utilities for environment configuration text formats.

This module provides parsers for:
- Environment variables (KEY=VALUE format)
- Docker mount paths (line-separated format)
"""


def parse_env_vars_text(text: str) -> tuple[dict[str, str], list[str]]:
    """
    Parse environment variables from text format.
    
    Supports KEY=VALUE format with comments (#) and empty lines.
    
    Args:
        text: Multi-line string with KEY=VALUE format
        
    Returns:
        Tuple of (parsed vars dict, list of error messages)
        
    Example:
        >>> parse_env_vars_text("KEY=value\\n# comment\\nKEY2=value2")
        ({'KEY': 'value', 'KEY2': 'value2'}, [])
    """
    parsed: dict[str, str] = {}
    errors: list[str] = []
    for idx, raw in enumerate((text or "").splitlines(), start=1):
        line: str = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"line {idx}: missing '='")
            continue
        key: str
        value: str
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            errors.append(f"line {idx}: empty key")
            continue
        parsed[key] = value
    return parsed, errors


def parse_mounts_text(text: str) -> list[str]:
    """
    Parse mount paths from text format.
    
    Filters out comments (#) and empty lines.
    
    Args:
        text: Multi-line string with one mount path per line
        
    Returns:
        List of mount paths (comments and empty lines filtered out)
        
    Example:
        >>> parse_mounts_text("/host/path:/container/path\\n# comment\\n/another:/path")
        ['/host/path:/container/path', '/another:/path']
    """
    mounts: list[str] = []
    for raw in (text or "").splitlines():
        line: str = raw.strip()
        if not line or line.startswith("#"):
            continue
        mounts.append(line)
    return mounts
