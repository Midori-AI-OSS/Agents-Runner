# First-run Docker check (PixelArch pull + hello world)

## Goal
Help new users validate Docker is usable (daemon/socket + image pull + container run) during first-run onboarding, without requiring persistence or long setup steps.

## Proposed UX
- Add a `Check Docker` button to the first-run screen (`FirstRunSetupDialog`) that runs a short Docker “smoke test”.
- Show progress/logs similar in spirit to the clone-test flow (user can proceed without waiting, but gets clear success/failure signal).
- On failure, show the error output and provide a link to Docker setup instructions: `https://io.midori-ai.xyz/support/dockersetup/`

## Smoke test behavior
- Pull PixelArch image and run a trivial command that produces visible output:
  - `docker pull lunamidori5/pixelarch:emerald`
  - `docker run --rm lunamidori5/pixelarch:emerald /bin/bash -lc 'echo hello world'`

## Implementation notes
- Prefer reusing the existing preflight worker/task plumbing:
  - `DockerPreflightWorker` already logs `docker pull ...` and runs a short container lifecycle.
  - Provide a minimal preflight script that only prints `hello world` so the logs prove the container actually executed.
- First-run runs before `MainWindow` exists:
  - use the existing “launch terminal + poll” approach (like the clone test) to keep the UI simple.

## Acceptance criteria
- Clicking `Check Docker` results in a clear pass/fail within a short timeout.
- Success shows the pulled image + `hello world` output in the UI or terminal.
- Failure surfaces a human-readable reason (missing docker CLI, daemon/socket permissions, etc.) and links the user to `https://io.midori-ai.xyz/support/dockersetup/`
