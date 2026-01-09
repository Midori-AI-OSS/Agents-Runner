import os
import re
import shutil
import subprocess


def validate_github_token_format(token: str) -> tuple[bool, str]:
    """Validate GitHub token format using known GitHub token patterns.
    
    GitHub tokens follow the format: {prefix}_{base62_string}
    Valid prefixes: ghp_ (Personal), gho_ (OAuth), ghu_ (User-to-Server),
                    ghr_ (Refresh), ghs_ (Server-to-Server)
    
    Args:
        token: The token string to validate.
        
    Returns:
        A tuple of (is_valid, error_message).
        - is_valid: True if token matches a known GitHub token pattern
        - error_message: Empty string if valid, otherwise describes the issue
        
    Examples:
        >>> validate_github_token_format("ghp_1234567890abcdefghij")
        (True, "")
        >>> validate_github_token_format("invalid")
        (False, "Invalid token format. Expected format: ghp_XXXX, gho_XXXX, ...")
    """
    token = (token or "").strip()
    
    if not token:
        return (False, "Empty token")
    
    # Check minimum length: prefix (3) + underscore (1) + payload (20 min) = 24
    if len(token) < 24:
        return (False, "Token too short (minimum 24 characters: prefix + underscore + 20+ character payload)")
    
    # Check for valid GitHub token prefix
    valid_prefixes = ("ghp_", "gho_", "ghu_", "ghr_", "ghs_")
    if not any(token.startswith(prefix) for prefix in valid_prefixes):
        return (False, f"Invalid token prefix. Expected one of: {', '.join(valid_prefixes)}")
    
    # Validate against GitHub token patterns (base62: A-Za-z0-9)
    # Reuse the same patterns as token_redaction.py for consistency
    github_token_patterns = [
        re.compile(r"^ghp_[A-Za-z0-9]{20,}$"),  # Personal Access Token
        re.compile(r"^gho_[A-Za-z0-9]{20,}$"),  # OAuth token
        re.compile(r"^ghu_[A-Za-z0-9]{20,}$"),  # User-to-Server token
        re.compile(r"^ghr_[A-Za-z0-9]{20,}$"),  # Refresh token
        re.compile(r"^ghs_[A-Za-z0-9]{20,}$"),  # Server-to-Server token
    ]
    
    for pattern in github_token_patterns:
        if pattern.match(token):
            return (True, "")
    
    # If we get here, prefix was valid but character set is wrong
    return (False, "Invalid token format. Token must contain only alphanumeric characters after the prefix")


def resolve_github_token(
    *, host: str = "github.com", timeout_s: float = 8.0, validate: bool = False
) -> str | None:
    """Return a GitHub token from the host environment or `gh`, if available.

    Preference order:
      1) `GH_TOKEN`
      2) `GITHUB_TOKEN`
      3) `gh auth token -h <host>`
      
    Args:
        host: The GitHub host to authenticate with (default: "github.com")
        timeout_s: Timeout in seconds for gh CLI calls (default: 8.0)
        validate: If True, validate token format before returning (default: False for backward compatibility)
        
    Returns:
        A valid GitHub token if found and validated, None otherwise.
        
    Raises:
        ValueError: If validate=True and token format is invalid.
    """

    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = (os.environ.get(key) or "").strip()
        if value:
            if validate:
                is_valid, error_msg = validate_github_token_format(value)
                if not is_valid:
                    raise ValueError(
                        f"GitHub token from {key} environment variable is invalid: {error_msg}\n"
                        f"Please check your token at https://github.com/settings/tokens or run 'gh auth login'"
                    )
            return value

    if shutil.which("gh") is None:
        return None

    try:
        proc = subprocess.run(
            [
                "gh",
                "auth",
                "token",
                "-h",
                str(host or "github.com").strip() or "github.com",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if proc.returncode != 0:
        return None

    raw = (proc.stdout or "").strip()
    if not raw:
        return None
    first = raw.splitlines()[0].strip()
    
    if first and validate:
        is_valid, error_msg = validate_github_token_format(first)
        if not is_valid:
            raise ValueError(
                f"GitHub token from 'gh auth token' is invalid: {error_msg}\n"
                f"Please re-authenticate with 'gh auth login'"
            )
    
    return first or None


def resolve_and_validate_github_token(
    *, host: str = "github.com", timeout_s: float = 8.0
) -> str | None:
    """Return a validated GitHub token from the host environment or `gh`, if available.
    
    This is a convenience wrapper around resolve_github_token() with validation enabled.
    It provides better error messages for invalid tokens at configuration time rather
    than waiting for failures deep in container execution.
    
    Args:
        host: The GitHub host to authenticate with (default: "github.com")
        timeout_s: Timeout in seconds for gh CLI calls (default: 8.0)
        
    Returns:
        A validated GitHub token if found, None if no token is available.
        
    Raises:
        ValueError: If a token is found but has an invalid format.
        
    Example:
        >>> token = resolve_and_validate_github_token()
        >>> if token:
        >>>     print("Valid GitHub token found")
        >>> else:
        >>>     print("No GitHub token available")
    """
    return resolve_github_token(host=host, timeout_s=timeout_s, validate=True)
