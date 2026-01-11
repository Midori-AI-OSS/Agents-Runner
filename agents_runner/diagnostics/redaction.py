"""Secret redaction utilities for diagnostics system."""

import re


# Patterns for detecting sensitive information
# Case-insensitive patterns for common secret keys
SECRET_KEY_PATTERN = re.compile(
    r'(?i)(authorization|bearer|token|api[_-]?key|secret|password|cookie)[:\s=]+([^\s\n]+)',
    re.IGNORECASE
)

# GitHub token patterns (ghp_, gho_, ghs_, ghu_, ghr_)
GITHUB_TOKEN_PATTERN = re.compile(
    r'\b(gh[pousr]_[a-zA-Z0-9]{36,255})\b'
)

# Generic base64-like tokens (at least 20 chars of alphanumeric+special)
GENERIC_TOKEN_PATTERN = re.compile(
    r'\b([a-zA-Z0-9+/]{40,}={0,2})\b'
)

# Authorization header with Bearer token
AUTH_HEADER_PATTERN = re.compile(
    r'(?i)authorization:\s*bearer\s+[^\s\n]+',
    re.IGNORECASE
)

# Cookie header
COOKIE_PATTERN = re.compile(
    r'(?i)cookie:\s*[^\n]+',
    re.IGNORECASE
)

# Key-value pairs with sensitive names
KEY_VALUE_PATTERN = re.compile(
    r'(?i)(token|api_?key|secret|password|access_?token|refresh_?token)(["\']?)\s*[:=]\s*(["\']?)([^\s\n,}\]"\']+)',
    re.IGNORECASE
)


def redact_secrets(text: str) -> str:
    """
    Redact sensitive information from text content.
    
    This function identifies and replaces:
    - Authorization headers (Bearer tokens)
    - Cookie values
    - API keys, tokens, secrets, passwords
    - GitHub tokens (ghp_, gho_, ghs_, etc.)
    - Generic long token-like strings
    
    Args:
        text: Input text that may contain sensitive information
        
    Returns:
        Text with sensitive values replaced with [REDACTED]
    """
    if not text:
        return text
    
    # Redact authorization headers
    text = AUTH_HEADER_PATTERN.sub('Authorization: Bearer [REDACTED]', text)
    
    # Redact cookie headers
    text = COOKIE_PATTERN.sub('Cookie: [REDACTED]', text)
    
    # Redact GitHub tokens
    text = GITHUB_TOKEN_PATTERN.sub('[REDACTED]', text)
    
    # Redact key-value pairs with sensitive keys
    def replace_key_value(match: re.Match) -> str:
        key = match.group(1)
        quote1 = match.group(2) or ''
        quote2 = match.group(3) or ''
        return f'{key}{quote1}:{quote2}[REDACTED]'
    
    text = KEY_VALUE_PATTERN.sub(replace_key_value, text)
    
    # Redact remaining secret key patterns
    def replace_secret(match: re.Match) -> str:
        key = match.group(1)
        return f'{key}: [REDACTED]'
    
    text = SECRET_KEY_PATTERN.sub(replace_secret, text)
    
    return text


def redact_lines(lines: list[str]) -> list[str]:
    """
    Redact sensitive information from a list of text lines.
    
    Args:
        lines: List of text lines that may contain sensitive information
        
    Returns:
        List of lines with sensitive values redacted
    """
    return [redact_secrets(line) for line in lines]
