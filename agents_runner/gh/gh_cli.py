import shutil


def is_gh_available() -> bool:
    return shutil.which("gh") is not None
