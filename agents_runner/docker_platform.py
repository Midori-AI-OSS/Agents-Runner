import os
import platform
import shutil
import subprocess


ROSETTA_INSTALL_COMMAND = "softwareupdate --install-rosetta --agree-to-license"


def _mac_hardware_is_apple_silicon() -> bool:
    sysctl = shutil.which("sysctl") or "/usr/sbin/sysctl"
    if not os.path.exists(sysctl):
        return False
    try:
        completed = subprocess.run(
            [sysctl, "-n", "hw.optional.arm64"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return str(completed.stdout or "").strip() == "1"


def docker_platform_for_pixelarch() -> str | None:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin" and (
        machine in {"arm64", "aarch64"} or _mac_hardware_is_apple_silicon()
    ):
        return "linux/amd64"
    return None


def docker_platform_args_for_pixelarch() -> list[str]:
    forced = docker_platform_for_pixelarch()
    if forced:
        return [f"--platform={forced}"]
    return []


def has_rosetta() -> bool | None:
    if docker_platform_for_pixelarch() != "linux/amd64":
        return None

    pkgutil = shutil.which("pkgutil") or "/usr/sbin/pkgutil"
    if not os.path.exists(pkgutil):
        return None

    try:
        completed = subprocess.run(
            [pkgutil, "--pkg-info", "com.apple.pkg.RosettaUpdateAuto"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    return completed.returncode == 0
