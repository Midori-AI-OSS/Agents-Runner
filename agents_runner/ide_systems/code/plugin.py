from __future__ import annotations

from agents_runner.ide_systems.models import IdeSystemSpec

PLUGIN = IdeSystemSpec(
    name="code",
    display_name="Code OSS",
    package_name="code",
    executable="code",
    launch_args=("--no-sandbox",),
    wait_process_pattern="comm=code|code-oss",
)
