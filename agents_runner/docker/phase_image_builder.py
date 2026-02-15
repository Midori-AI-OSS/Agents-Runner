"""Layered Docker image cache builder for preflight phases."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from agents_runner.docker.process import has_image
from agents_runner.docker.process import run_docker
from agents_runner.log_format import format_log

logger = logging.getLogger(__name__)

PREFLIGHTS_DIR = Path(__file__).parent.parent / "preflights"


def _compute_content_hash(content: str) -> str:
    sha256 = hashlib.sha256()
    sha256.update(content.encode("utf-8"))
    return sha256.hexdigest()[:16]


def _compute_file_hash(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def _compute_preflights_hash(preflights_dir: Path) -> str:
    if not preflights_dir.exists():
        return "missing"
    digest = hashlib.sha256()
    for path in sorted(preflights_dir.glob("*.sh")):
        digest.update(path.name.encode("utf-8"))
        digest.update(_compute_file_hash(path).encode("utf-8"))
    return digest.hexdigest()[:16]


def _get_base_image_digest(base_image: str) -> str:
    try:
        raw = run_docker(["image", "inspect", base_image], timeout_s=30.0)
        payload = json.loads(raw)
        if payload and len(payload) > 0:
            image_id = str(payload[0].get("Id", "") or "")
            if image_id.startswith("sha256:"):
                image_id = image_id[7:]
            if image_id:
                return image_id[:16]
    except Exception:
        pass
    return hashlib.sha256(base_image.encode("utf-8")).hexdigest()[:16]


def _resolve_bundled_script_name(
    script_content: str,
    *,
    preflights_dir: Path,
) -> str | None:
    target = str(script_content or "").strip()
    if not target:
        return None
    try:
        for candidate in sorted(preflights_dir.glob("*.sh")):
            content = candidate.read_text(encoding="utf-8").strip()
            if content == target:
                return candidate.name
    except Exception:
        return None
    return None


def _get_dockerfile_template(
    *,
    base_image: str,
    run_cmd: str,
    include_custom_script: bool,
) -> str:
    custom_copy = "COPY phase_script.sh /tmp/agents-runner-phase-script.sh\n"
    if not include_custom_script:
        custom_copy = ""
    return (
        f"FROM {base_image}\n\n"
        "COPY preflights/ /tmp/agents-runner-preflights/\n"
        f"{custom_copy}\n"
        f"RUN {run_cmd}\n"
    )


def compute_phase_cache_key(
    *,
    base_image: str,
    phase_name: str,
    script_content: str,
    preflights_dir: Path,
    script_source: str,
) -> str:
    base_digest = _get_base_image_digest(base_image)
    phase_hash = _compute_content_hash(str(phase_name or "phase"))
    script_hash = _compute_content_hash(str(script_content or ""))
    preflights_hash = _compute_preflights_hash(preflights_dir)
    source_hash = _compute_content_hash(script_source)
    return f"{base_digest}-{phase_hash}-{script_hash}-{preflights_hash}-{source_hash}"


def build_phase_image(
    *,
    base_image: str,
    tag: str,
    phase_name: str,
    script_content: str,
    preflights_dir: Path,
    on_log: Callable[[str], None] | None = None,
) -> None:
    if on_log is None:
        on_log = logger.info

    if not preflights_dir.is_dir():
        raise FileNotFoundError(f"Preflights directory not found: {preflights_dir}")

    script_name = _resolve_bundled_script_name(
        script_content, preflights_dir=preflights_dir
    )
    include_custom_script = script_name is None

    if include_custom_script:
        run_cmd = (
            "/bin/bash /tmp/agents-runner-phase-script.sh "
            "&& sudo rm -f /tmp/agents-runner-phase-script.sh "
            "&& sudo rm -rf /tmp/agents-runner-preflights"
        )
        script_source = "custom"
    else:
        run_cmd = (
            f"/bin/bash /tmp/agents-runner-preflights/{script_name} "
            "&& sudo rm -rf /tmp/agents-runner-preflights"
        )
        script_source = f"bundled:{script_name}"

    dockerfile_template = _get_dockerfile_template(
        base_image=base_image,
        run_cmd=run_cmd,
        include_custom_script=include_custom_script,
    )
    dockerfile_hash = _compute_content_hash(dockerfile_template)
    on_log(
        format_log(
            "phase",
            "build",
            "INFO",
            f"building {phase_name} layer image: {tag} ({script_source})",
        )
    )

    with tempfile.TemporaryDirectory() as build_dir:
        build_path = Path(build_dir)

        # Keep the script directory available for scripts that source siblings.
        import shutil

        shutil.copytree(preflights_dir, build_path / "preflights")

        if include_custom_script:
            script_path = build_path / "phase_script.sh"
            script_text = str(script_content or "")
            if not script_text.endswith("\n"):
                script_text += "\n"
            script_path.write_text(script_text, encoding="utf-8")

        dockerfile_path = build_path / "Dockerfile"
        dockerfile_path.write_text(dockerfile_template, encoding="utf-8")

        on_log(
            format_log(
                "phase",
                "build",
                "INFO",
                f"{phase_name} dockerfile hash: {dockerfile_hash}",
            )
        )

        build_args = [
            "build",
            "-t",
            tag,
            "-f",
            str(dockerfile_path),
            str(build_path),
        ]
        process = subprocess.Popen(
            ["docker", *build_args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if process.stdout:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    on_log(format_log("phase", "build", "INFO", line))
        code = process.wait(timeout=900.0)
        if code != 0:
            raise RuntimeError(f"Docker build failed with exit code {code}")


def ensure_phase_image(
    *,
    base_image: str,
    phase_name: str,
    script_content: str,
    preflights_dir: Path | None = None,
    on_log: Callable[[str], None] | None = None,
) -> str:
    if on_log is None:
        on_log = logger.info

    content = str(script_content or "").strip()
    if not content:
        return base_image

    phase = "".join(
        ch
        for ch in str(phase_name or "phase").strip().lower()
        if ch.isalnum() or ch in {"-", "_"}
    )
    if not phase:
        phase = "phase"

    preflights = preflights_dir or PREFLIGHTS_DIR
    script_name = _resolve_bundled_script_name(content, preflights_dir=preflights)
    script_source = f"bundled:{script_name}" if script_name else "custom"

    key = compute_phase_cache_key(
        base_image=base_image,
        phase_name=phase,
        script_content=content,
        preflights_dir=preflights,
        script_source=script_source,
    )
    tag = f"agent-runner-phase-{phase}:{key}"

    if has_image(tag):
        on_log(
            format_log(
                "phase",
                "cache",
                "INFO",
                f"{phase}: cache hit -> {tag}",
            )
        )
        return tag

    on_log(
        format_log(
            "phase",
            "cache",
            "INFO",
            f"{phase}: cache miss; building {tag}",
        )
    )
    try:
        build_phase_image(
            base_image=base_image,
            tag=tag,
            phase_name=phase,
            script_content=content,
            preflights_dir=preflights,
            on_log=on_log,
        )
        on_log(
            format_log(
                "phase",
                "cache",
                "INFO",
                f"{phase}: built -> {tag}",
            )
        )
        return tag
    except Exception as exc:
        on_log(
            format_log(
                "phase",
                "cache",
                "WARN",
                f"{phase}: build failed ({exc}); falling back to runtime phase",
            )
        )
        return base_image
