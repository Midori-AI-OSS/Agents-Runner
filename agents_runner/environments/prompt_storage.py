import os
import uuid


def user_prompts_dir() -> str:
    """Returns the directory path for user-defined prompts.
    
    Returns:
        Path to ~/.midoriai/agents-runner/prompts
    """
    home = os.path.expanduser("~")
    return os.path.join(home, ".midoriai", "agents-runner", "prompts")


def ensure_user_prompts_dir() -> str:
    """Creates the prompts directory if it doesn't exist.
    
    Returns:
        Path to the prompts directory
    """
    prompts_dir = user_prompts_dir()
    os.makedirs(prompts_dir, exist_ok=True)
    return prompts_dir


def generate_prompt_filename() -> str:
    """Generates a unique filename for a prompt file.
    
    Returns:
        Filename in format: {uuid}.md
    """
    return f"{uuid.uuid4()}.md"


def save_prompt_to_file(text: str, filename: str | None = None) -> str:
    """Saves prompt text to a file.
    
    Args:
        text: The prompt text to save
        filename: Optional filename (if not provided, generates UUID-based name)
    
    Returns:
        Full path to the saved file
    
    Raises:
        OSError: If file creation or writing fails
    """
    prompts_dir = ensure_user_prompts_dir()
    if filename is None:
        filename = generate_prompt_filename()
    
    file_path = os.path.join(prompts_dir, filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)
    
    return file_path


def load_prompt_from_file(path: str) -> str:
    """Loads prompt text from a file.
    
    Args:
        path: Full path to the prompt file
    
    Returns:
        The prompt text content
    
    Raises:
        FileNotFoundError: If the file doesn't exist
        OSError: If file reading fails
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def delete_prompt_file(path: str) -> None:
    """Deletes a prompt file.
    
    Args:
        path: Full path to the prompt file
    
    Raises:
        OSError: If file deletion fails
    """
    if os.path.exists(path):
        os.unlink(path)
