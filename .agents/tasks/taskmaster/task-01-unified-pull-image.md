# Task 01: Unified pull_image Refactor

## Summary

Replace the simple blocking `pull_image()` in `agents_runner/docker/process.py` with a streaming implementation that supports cancellation via `check_stop` predicate and per-line log forwarding via `on_log`. Wire it up across the agent worker, worker setup, and interactive prep worker.

## Files Changed (4)

### 1. agents_runner/docker/process.py

**Imports:** Add `selectors`, `time`, and `Callable` to the import block.

Current imports (lines 1-4):
```python
import json
import subprocess

from typing import Any
```

New imports:
```python
import json
import selectors
import subprocess
import time
from collections.abc import Callable
from typing import Any
```

**Function:** Replace the current 2-line `pull_image()` (lines 62-63):
```python
def pull_image(image: str, *, platform_args: list[str]) -> None:
    run_docker(["pull", *list(platform_args or []), image], timeout_s=600.0)
```

With the full streaming implementation:

```python
def pull_image(
    image: str,
    *,
    platform_args: list[str] | None = None,
    on_log: Callable[[str], None] | None = None,
    check_stop: Callable[[], bool] | None = None,
    timeout_s: float = 600.0,
) -> None:
    cmd = ["docker", "pull", *(platform_args or []), image]
    start_s = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None:
        raise RuntimeError("docker pull: failed to open stdout pipe")
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    try:
        while True:
            elapsed = time.monotonic() - start_s
            if elapsed > timeout_s:
                if proc.poll() is not None:
                    break
                proc.kill()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    pass
                raise TimeoutError(f"docker pull timed out after {timeout_s:.0f}s: {image}")
            if check_stop is not None and check_stop():
                proc.kill()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    pass
                raise RuntimeError("docker pull cancelled")
            ready = sel.select(timeout=0.1)
            for key, _mask in ready:
                line = key.fileobj.readline()
                if line:
                    if on_log is not None:
                        on_log(line.rstrip("\n"))
                else:
                    break
            if proc.poll() is not None:
                for key, _mask in sel.select(timeout=0):
                    remaining = key.fileobj.read()
                    if remaining and on_log is not None:
                        for rline in remaining.splitlines():
                            on_log(rline)
                break
    finally:
        sel.close()
    if proc.returncode != 0:
        raise RuntimeError(f"docker pull failed with exit code {proc.returncode}: {image}")
```

**Do not change:** `run_docker`, `inspect_state`, `has_image`, `has_platform_image`.

### 2. agents_runner/docker/agent_worker.py

**New method `_check_stop`:** Insert after `request_kill` (after line 90) and before `run()` (line 92):

```python
    def _check_stop(self) -> bool:
        """Return True if a stop has been requested."""
        return self._stop.is_set()
```

**Modify `WorkerSetup` call at line 121.** Change from:
```python
            setup = WorkerSetup(self._config, self._prompt, self._on_log, self._on_state)
```
To:
```python
            setup = WorkerSetup(self._config, self._prompt, self._on_log, self._on_state, check_stop=self._check_stop)
```

### 3. agents_runner/docker/agent_worker_setup.py

**WorkerSetup.__init__ signature:** Add `check_stop: Callable[[], bool] | None = None` parameter after `on_state`:

Current (lines 93-98):
```python
    def __init__(
        self,
        config: DockerRunnerConfig,
        prompt: str,
        on_log: Callable[[str], None],
        on_state: Callable[[dict[str, Any]], None],
    ) -> None:
```

New:
```python
    def __init__(
        self,
        config: DockerRunnerConfig,
        prompt: str,
        on_log: Callable[[str], None],
        on_state: Callable[[dict[str, Any]], None],
        check_stop: Callable[[], bool] | None = None,
    ) -> None:
```

**Store the predicate:** Add after `self._on_state = on_state` (line 103):
```python
        self._check_stop = check_stop
```

**Modify `pull_image_if_needed` call (line 456):** Change from:
```python
            pull_image(self._config.image, platform_args=platform_args)
```
To:
```python
            pull_image(self._config.image, platform_args=platform_args, on_log=self._on_log, check_stop=self._check_stop)
```

### 4. agents_runner/ui/interactive_prep_worker.py

**Remove import:** Delete `import subprocess` at line 5 (no longer directly needed by this file).

**Add import:** After line 16 (`from agents_runner.docker.process import has_platform_image`), add on line 17:
```python
from agents_runner.docker.process import pull_image
```

**Replace `_pull_image` method (lines 146-183):** Replace the entire method with:

```python
    def _pull_image(self) -> None:
        pull_started_s = time.monotonic()
        platform_args = docker_platform_args_for_pixelarch()
        self._diag("INFO", f"docker pull start image={self._image}")
        self.log.emit(
            self._task_id,
            format_log(
                "docker",
                "cmd",
                "INFO",
                " ".join(shlex.quote(part) for part in ["docker", "pull", *platform_args, self._image]),
            ),
        )
        pull_image(
            self._image,
            platform_args=platform_args,
            on_log=lambda line: self.log.emit(self._task_id, format_log("docker", "pull", "INFO", str(line or "").strip())),
            check_stop=lambda: self._stop_requested,
        )
        pull_elapsed_ms = (time.monotonic() - pull_started_s) * 1000.0
        self._diag("INFO", f"docker pull done elapsed_ms={pull_elapsed_ms:.0f}")
```

## Key Design Points

- `check_stop` is a **predicate** (returns `bool`), not a raise-on-stop callable. The `pull_image` function raises `RuntimeError("docker pull cancelled")` when `check_stop()` returns `True`.
- `_stop_requested` is a `bool` attribute on `InteractivePrepWorker`, set to `True` by `request_stop()`. The lambda `lambda: self._stop_requested` evaluates it each time `pull_image` polls.
- For `DockerAgentWorker`, `_check_stop()` wraps `self._stop.is_set()` (a `threading.Event`).
- `on_log` receives individual lines without trailing newlines. The caller wraps each line into a formatted log entry.
- The streaming pull uses `selectors` for non-blocking I/O with a 100ms polling interval, checking `check_stop` and `timeout_s` on each iteration.

## Pre-commit Validation

- Run `uv run ruff format .`
- Run `uv run ruff check .`
- Run `uv run basedpyright`
- Verify `uv run main.py` launches without import errors
