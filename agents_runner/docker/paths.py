import os


def _is_git_repo_root(path: str) -> bool:
    return os.path.exists(os.path.join(path, ".git"))

