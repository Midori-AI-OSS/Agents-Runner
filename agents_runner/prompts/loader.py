"""Prompt loader utility for loading system prompts from markdown files.

This module provides functionality to load agent prompts from markdown files
with support for template variable substitution and fallback to hard-coded
defaults if files are missing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Cache for loaded prompts to avoid re-reading files
_PROMPT_CACHE: dict[str, str] = {}

# Directory containing prompt markdown files
PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs: Any) -> str:
    """Load a prompt from a markdown file with template variable substitution.
    
    Args:
        name: Prompt filename without extension (e.g., 'pixelarch_environment')
        **kwargs: Template variables to substitute (e.g., DISPLAY=':1')
    
    Returns:
        Formatted prompt string with variables substituted
        
    Raises:
        FileNotFoundError: If the prompt file does not exist
        RuntimeError: If the prompt file cannot be read or parsed
        
    Example:
        >>> load_prompt('headless_desktop', DISPLAY=':1')
        '\\n\\nDESKTOP (non-interactive only)\\n- X11 display: :1\\n...'
    """
    cache_key = name
    
    # Check cache first
    if cache_key not in _PROMPT_CACHE:
        prompt_file = PROMPTS_DIR / f"{name}.md"
        
        if not prompt_file.exists():
            error_msg = f"Prompt file not found: {prompt_file}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            # Read the entire file
            content = prompt_file.read_text(encoding="utf-8")
            
            # Extract the prompt section (everything after "## Prompt")
            if "## Prompt" in content:
                # Get everything after "## Prompt"
                # Remove single leading newline but keep any others (for spacing)
                # Strip trailing whitespace
                after_marker = content.split("## Prompt", 1)[1]
                if after_marker.startswith('\n'):
                    after_marker = after_marker[1:]
                prompt_text = after_marker.rstrip()
            else:
                # If no section marker, use entire file
                prompt_text = content.strip()
            
            _PROMPT_CACHE[cache_key] = prompt_text
            logger.debug(f"Loaded prompt from {prompt_file}")
            
        except FileNotFoundError:
            raise
        except Exception as e:
            error_msg = f"Failed to load prompt from {prompt_file}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    # Get prompt from cache
    prompt = _PROMPT_CACHE[cache_key]
    
    # Perform template variable substitution
    if kwargs:
        try:
            prompt = prompt.format(**kwargs)
        except KeyError as e:
            logger.error(
                f"Template variable missing in prompt '{name}': {e}, "
                f"using prompt without substitution"
            )
        except Exception as e:
            logger.error(
                f"Failed to substitute variables in prompt '{name}': {e}"
            )
    
    return prompt


def clear_cache() -> None:
    """Clear the prompt cache. Useful for testing or reloading prompts."""
    _PROMPT_CACHE.clear()
    logger.debug("Prompt cache cleared")
