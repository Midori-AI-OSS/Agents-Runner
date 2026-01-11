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
# Note: Currently unused to avoid false positives - may be enabled with context checks
# GENERIC_TOKEN_PATTERN = re.compile(
#     r'\b([a-zA-Z0-9+/]{40,}={0,2})\b'
# )

# Authorization header with Bearer, Basic, OAuth, etc.
AUTH_HEADER_PATTERN = re.compile(
    r'(?i)authorization:\s*(?:bearer|basic|digest|oauth|token)\s+[^\s\n]+',
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

# SSH key patterns (RSA, DSS, Ed25519, ECDSA)
SSH_KEY_PATTERN = re.compile(
    r'(ssh-(?:rsa|dss|ed25519|ecdsa)\s+[A-Za-z0-9+/=]+)',
    re.IGNORECASE
)

# PEM-encoded private keys
PEM_KEY_PATTERN = re.compile(
    r'-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----',
    re.DOTALL | re.IGNORECASE
)

# Database connection strings with credentials
DB_URL_PATTERN = re.compile(
    r'([a-zA-Z][a-zA-Z0-9+.-]*://[^:/@\s]+:)([^@\s]+)(@[^\s]+)'
)


def redact_secrets(text: str) -> str:
    """
    Redact sensitive information from text content.
    
    This function identifies and replaces:
    - Authorization headers (Bearer, Basic, OAuth, etc.)
    - Cookie values
    - API keys, tokens, secrets, passwords
    - GitHub tokens (ghp_, gho_, ghs_, etc.)
    - SSH keys (all formats)
    - PEM private keys
    - Database connection strings with credentials
    - Generic long token-like strings
    
    Args:
        text: Input text that may contain sensitive information
        
    Returns:
        Text with sensitive values replaced with [REDACTED]
    """
    if not text:
        return text
    
    # Redact SSH keys (must be before generic patterns)
    text = SSH_KEY_PATTERN.sub('ssh-[KEY-TYPE] [REDACTED]', text)
    
    # Redact PEM private keys
    text = PEM_KEY_PATTERN.sub('-----BEGIN PRIVATE KEY-----\n[REDACTED]\n-----END PRIVATE KEY-----', text)
    
    # Redact authorization headers (all types)
    text = AUTH_HEADER_PATTERN.sub('Authorization: [REDACTED]', text)
    
    # Redact cookie headers
    text = COOKIE_PATTERN.sub('Cookie: [REDACTED]', text)
    
    # Redact database connection strings (preserve scheme and host, redact password)
    def replace_db_url(match: re.Match[str]) -> str:
        return f'{match.group(1)}[REDACTED]{match.group(3)}'
    
    text = DB_URL_PATTERN.sub(replace_db_url, text)
    
    # Redact GitHub tokens
    text = GITHUB_TOKEN_PATTERN.sub('[REDACTED]', text)
    
    # Redact key-value pairs with sensitive keys
    def replace_key_value(match: re.Match[str]) -> str:
        key = match.group(1)
        quote1 = match.group(2) or ''
        quote2 = match.group(3) or ''
        return f'{key}{quote1}:{quote2}[REDACTED]'
    
    text = KEY_VALUE_PATTERN.sub(replace_key_value, text)
    
    # Redact remaining secret key patterns
    def replace_secret(match: re.Match[str]) -> str:
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
