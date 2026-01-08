# Part 3: Container Caching Architecture Diagrams

**Audit ID:** 3af660d3  
**Date:** 2025-01-24

---

## 1. Current Architecture (Part 2 - Desktop Caching Only)

```
┌─────────────────────────────────────────────────────────────────┐
│                        EXISTING SYSTEM                          │
└─────────────────────────────────────────────────────────────────┘

Toggle: cache_desktop_build (default: OFF)

When OFF (Runtime Installation):
┌─────────────────┐
│  Task Start     │
└────────┬────────┘
         │
         v
┌────────────────────────────────────────────┐
│  FROM lunamidori5/pixelarch:emerald       │
│                                            │
│  Runtime:                                  │
│    1. Install desktop (yay -S ...)        │  ← 45-90 seconds
│    2. Start services (Xvnc, fluxbox...)   │  ← 2-5 seconds
│    3. Run preflight script                │  ← Variable
│    4. Start agent                          │
└────────────────────────────────────────────┘


When ON (Cached Desktop):
┌─────────────────┐
│  Task Start     │
└────────┬────────┘
         │
         v
┌────────────────────────────────────────────┐
│  FROM agent-runner-desktop:abc123...       │  ← Pre-built image
│                                            │
│  Desktop already installed!                │
│                                            │
│  Runtime:                                  │
│    1. Start services (Xvnc, fluxbox...)   │  ← 2-5 seconds (FAST!)
│    2. Run preflight script                │  ← Variable
│    3. Start agent                          │
└────────────────────────────────────────────┘
         ^
         │ Built once, reused
         │
┌────────────────────────────────────────────┐
│  Image Build (one-time):                   │
│                                            │
│  FROM lunamidori5/pixelarch:emerald       │
│  RUN desktop_install.sh                    │  ← 45-90 seconds
│  RUN desktop_setup.sh                      │
│                                            │
│  → agent-runner-desktop:abc123...         │
└────────────────────────────────────────────┘
```

---

## 2. Proposed Architecture (Part 3 - Container Caching)

```
┌─────────────────────────────────────────────────────────────────┐
│                         NEW SYSTEM                              │
└─────────────────────────────────────────────────────────────────┘

Two INDEPENDENT toggles:
  1. cache_desktop_build (Part 2)
  2. cache_container_build (Part 3 - NEW)

Both can be ON simultaneously (layered images)
```

### Scenario A: Container Caching ON, Desktop OFF

```
┌─────────────────┐
│  Task Start     │
└────────┬────────┘
         │
         v
┌────────────────────────────────────────────┐
│  FROM agent-runner-env:xyz789...           │  ← Pre-built image
│                                            │
│  Packages already installed!               │
│                                            │
│  Runtime:                                  │
│    1. Run preflight (run_preflight.sh)    │  ← 2-3 seconds (FAST!)
│    2. Start agent                          │
└────────────────────────────────────────────┘
         ^
         │ Built once, reused
         │
┌────────────────────────────────────────────┐
│  Image Build (one-time):                   │
│                                            │
│  FROM lunamidori5/pixelarch:emerald       │
│  RUN cached_preflight.sh                   │  ← 10-60 seconds
│      └─ yay -S python nodejs               │     (packages)
│      └─ curl -O tool                       │
│                                            │
│  → agent-runner-env:xyz789...             │
└────────────────────────────────────────────┘
```

### Scenario B: Both Desktop + Container Caching ON

```
┌─────────────────┐
│  Task Start     │
└────────┬────────┘
         │
         v
┌────────────────────────────────────────────┐
│  FROM agent-runner-env:desktop-abc-xyz...  │  ← Pre-built image
│                                            │
│  Desktop + Packages already installed!     │
│                                            │
│  Runtime:                                  │
│    1. Start services (Xvnc, fluxbox...)   │  ← 2-3 seconds
│    2. Run preflight (run_preflight.sh)    │     (VERY FAST!)
│    3. Start agent                          │
└────────────────────────────────────────────┘
         ^
         │ Built once, reused
         │
┌────────────────────────────────────────────┐
│  Layer 2 Build:                            │
│                                            │
│  FROM agent-runner-desktop:abc123...      │  ← Layer 1 output
│  RUN cached_preflight.sh                   │  ← 10-60 seconds
│      └─ yay -S python nodejs               │     (packages)
│      └─ curl -O tool                       │
│                                            │
│  → agent-runner-env:desktop-abc-xyz...    │
└────────────────────────────────────────────┘
         ^
         │ Uses cached desktop
         │
┌────────────────────────────────────────────┐
│  Layer 1 Build:                            │
│                                            │
│  FROM lunamidori5/pixelarch:emerald       │
│  RUN desktop_install.sh                    │  ← 45-90 seconds
│  RUN desktop_setup.sh                      │     (desktop)
│                                            │
│  → agent-runner-desktop:abc123...         │
└────────────────────────────────────────────┘
```

---

## 3. Preflight Script Split

```
┌─────────────────────────────────────────────────────────────────┐
│                    SINGLE PREFLIGHT (OLD)                       │
└─────────────────────────────────────────────────────────────────┘

  preflight_script:
    #!/bin/bash
    yay -S python nodejs              ← Slow (30-60s)
    curl -O /usr/local/bin/tool       ← Slow (5-10s)
    export API_KEY=${TASK_KEY}        ← Fast (instant)
    mkdir -p /tmp/workspace-${TASK}   ← Fast (instant)

  Runs at: TASK START
  Duration: 40-90 seconds every time


┌─────────────────────────────────────────────────────────────────┐
│                    SPLIT PREFLIGHT (NEW)                        │
└─────────────────────────────────────────────────────────────────┘

  cached_preflight_script:              run_preflight_script:
    #!/bin/bash                           #!/bin/bash
    yay -S python nodejs                  export API_KEY=${TASK_KEY}
    curl -O /usr/local/bin/tool           mkdir -p /tmp/workspace-${TASK}

  Runs at: IMAGE BUILD TIME              Runs at: TASK START
  Duration: 40-90 seconds (once)          Duration: 2-3 seconds (every time)
  Benefit: CACHED!                        Benefit: FAST!

  Total first run: 40-90s + 2-3s = 45-93s
  Total next runs: 0s + 2-3s = 2-3s  ← 15-30x faster!
```

---

## 4. Cache Key Computation

```
┌─────────────────────────────────────────────────────────────────┐
│                    DESKTOP CACHE KEY (Part 2)                   │
└─────────────────────────────────────────────────────────────────┘

  Inputs:
    1. Base image: lunamidori5/pixelarch:emerald
       → digest: abc123def456 (first 16 chars of sha256)
    
    2. desktop_install.sh
       → hash: 7890abcd1234
    
    3. desktop_setup.sh
       → hash: ef567890abcd
    
    4. Dockerfile template
       → hash: 1234567890ab

  Output:
    emerald-abc123def456-7890abcd1234-ef567890abcd-1234567890ab
    └─────┘ └───────────┘ └──────────┘ └──────────┘ └──────────┘
      │         │              │             │            │
    variant  base digest   install.sh   setup.sh   dockerfile


┌─────────────────────────────────────────────────────────────────┐
│                 ENVIRONMENT CACHE KEY (Part 3 - NEW)            │
└─────────────────────────────────────────────────────────────────┘

  Scenario A: Desktop OFF

    Inputs:
      1. Base image: lunamidori5/pixelarch:emerald
         → digest: abc123def456
      
      2. cached_preflight_script
         → hash: xyz789012345
      
      3. Env Dockerfile template
         → hash: 654321fedcba

    Output:
      emerald-abc123def456-xyz789012345-654321fedcba
      └─────┘ └───────────┘ └──────────┘ └──────────┘
        │         │              │             │
      variant  base digest   preflight   dockerfile


  Scenario B: Desktop ON

    Inputs:
      1. Desktop image: agent-runner-desktop:emerald-abc123-def456-xyz789-012345
         → key: emerald-abc123-def456-xyz789-012345
      
      2. cached_preflight_script
         → hash: a1b2c3d4e5f6
      
      3. Env Dockerfile template
         → hash: 6f7e8d9c0b1a

    Output:
      desktop-emerald-abc123-def456-xyz789-012345-a1b2c3d4-6f7e8d9c
      └──────┘└────────────────────────────────────┘└──────────┘└────────┘
         │              │                              │           │
      prefix      desktop cache key              preflight   dockerfile

      Note: "desktop-" prefix indicates layered build
```

---

## 5. Data Flow: Task Execution

```
┌─────────────────────────────────────────────────────────────────┐
│                      TASK EXECUTION FLOW                        │
└─────────────────────────────────────────────────────────────────┘

User Action: "Start Task"
│
├─ UI: main_window_tasks_agent.py
│  │
│  ├─ Load Environment from: environments/model.py
│  │  └─ Fields: cache_desktop_build, cache_container_build,
│  │             cached_preflight_script, run_preflight_script
│  │
│  └─ Build DockerRunnerConfig from: docker/config.py
│     └─ Fields: desktop_cache_enabled, container_cache_enabled,
│                cached_preflight_script, run_preflight_script
│
├─ Supervisor: execution/supervisor.py
│  │
│  └─ Create DockerAgentWorker
│
├─ Worker: docker/agent_worker.py
│  │
│  ├─ Step 1: Pull base image (if needed)
│  │           lunamidori5/pixelarch:emerald
│  │
│  ├─ Step 2: Desktop caching (if enabled)
│  │  │
│  │  └─ Call: image_builder.ensure_desktop_image()
│  │     │
│  │     ├─ Check: agent-runner-desktop:abc123... exists?
│  │     │  ├─ YES: Use cached image
│  │     │  └─ NO:  Build new image
│  │     │          │
│  │     │          ├─ Create Dockerfile
│  │     │          ├─ Copy desktop_install.sh, desktop_setup.sh
│  │     │          ├─ RUN install + setup
│  │     │          └─ Tag: agent-runner-desktop:abc123...
│  │     │
│  │     └─ Return: agent-runner-desktop:abc123... (or base on failure)
│  │
│  ├─ Step 3: Container caching (if enabled) ← NEW!
│  │  │
│  │  └─ Call: env_image_builder.ensure_env_image()
│  │     │
│  │     ├─ Input: base_image (desktop image or pixelarch)
│  │     │         cached_preflight_script
│  │     │         desktop_enabled, desktop_cached
│  │     │
│  │     ├─ Compute: env cache key
│  │     │
│  │     ├─ Check: agent-runner-env:xyz789... exists?
│  │     │  ├─ YES: Use cached image
│  │     │  └─ NO:  Build new image
│  │     │          │
│  │     │          ├─ Create Dockerfile
│  │     │          ├─ Copy cached_preflight.sh
│  │     │          ├─ RUN cached_preflight.sh
│  │     │          └─ Tag: agent-runner-env:xyz789...
│  │     │
│  │     └─ Return: agent-runner-env:xyz789... (or base on failure)
│  │
│  ├─ Step 4: Build preflight_clause
│  │  │
│  │  ├─ Settings preflight (if set)
│  │  │  └─ Add: /bin/bash /tmp/preflight-settings.sh
│  │  │
│  │  ├─ Run preflight (if set) ← NEW!
│  │  │  └─ Add: /bin/bash /tmp/preflight-run.sh
│  │  │
│  │  └─ Legacy environment preflight (backward compat)
│  │     └─ Add: /bin/bash /tmp/preflight-environment.sh
│  │
│  ├─ Step 5: Build docker run command
│  │  │
│  │  └─ docker run ... {runtime_image} /bin/bash -lc "
│  │      set -euo pipefail;
│  │      {preflight_clause}
│  │      {agent_command}
│  │    "
│  │
│  └─ Step 6: Execute container
│     │
│     ├─ Stream logs to UI
│     ├─ Monitor container state
│     └─ Collect artifacts
│
└─ Result: Task complete
```

---

## 6. UI Layout Changes

```
┌─────────────────────────────────────────────────────────────────┐
│                   ENVIRONMENT SETTINGS PAGE                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  General Tab                                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Headless desktop:                                              │
│    ☑ Enable headless desktop                                   │
│    ☑ Cache desktop build        ← Part 2                       │
│    ☑ Enable container caching   ← Part 3 NEW!                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Preflight Tab                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Preflight Mode:                                                │
│    ○ Single preflight (legacy)                                 │
│    ● Split preflight (container caching)    ← NEW!             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Tab: Cached Preflight                                   │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │                                                         │   │
│  │  #!/bin/bash                                            │   │
│  │  # Runs at IMAGE BUILD TIME                            │   │
│  │  # Put here: package installs, downloads, static setup │   │
│  │                                                         │   │
│  │  yay -S python nodejs                                   │   │
│  │  curl -O /usr/local/bin/tool                           │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Tab: Run Preflight                                      │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │                                                         │   │
│  │  #!/bin/bash                                            │   │
│  │  # Runs at TASK START                                  │   │
│  │  # Put here: env vars, per-task setup                  │   │
│  │                                                         │   │
│  │  export API_KEY=${TASK_KEY}                            │   │
│  │  mkdir -p /tmp/workspace-${TASK_ID}                    │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Auto-split Helper]  [Validate Scripts]                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Performance Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│                     PERFORMANCE TIMELINE                        │
└─────────────────────────────────────────────────────────────────┘

Scenario: User runs the same task 5 times

Configuration A: NO CACHING (Baseline)
  Run 1: ████████████████████████████████████████████ 90s
  Run 2: ████████████████████████████████████████████ 90s
  Run 3: ████████████████████████████████████████████ 90s
  Run 4: ████████████████████████████████████████████ 90s
  Run 5: ████████████████████████████████████████████ 90s
  Total: 450 seconds


Configuration B: DESKTOP CACHING (Part 2)
  Build: ██████████████████████████████████████████████████ 90s (one-time)
  Run 1: ██ 5s
  Run 2: ██ 5s
  Run 3: ██ 5s
  Run 4: ██ 5s
  Run 5: ██ 5s
  Total: 115 seconds (3.9x faster!)


Configuration C: CONTAINER CACHING (Part 3)
  Build: ████████████████████████████ 60s (one-time)
  Run 1: █ 3s
  Run 2: █ 3s
  Run 3: █ 3s
  Run 4: █ 3s
  Run 5: █ 3s
  Total: 75 seconds (6x faster!)


Configuration D: BOTH CACHES (Part 2 + Part 3)
  Build: ██████████████████████████████████████████████████████████ 120s (one-time)
  Run 1: █ 3s
  Run 2: █ 3s
  Run 3: █ 3s
  Run 4: █ 3s
  Run 5: █ 3s
  Total: 135 seconds (3.3x faster!)
  
  But after 6 runs: Break-even!
  Runs 6-10: 15 seconds vs 450 seconds (30x faster!)


Break-even Analysis:
  Desktop only:  Break-even at run 2
  Container only: Break-even at run 3
  Both caches:   Break-even at run 3
```

---

## 8. Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ERROR HANDLING STRATEGY                      │
└─────────────────────────────────────────────────────────────────┘

Image Build Process:
│
├─ Try: Build desktop image
│  ├─ Success: Use cached desktop
│  └─ Failure: Fall back to pixelarch base
│              Log error, continue with runtime install
│
├─ Try: Build env image
│  ├─ Success: Use cached env
│  └─ Failure: Fall back to desktop/base
│              Log error, continue with runtime preflight
│
└─ Result: Task never fails due to cache build failure
           Worst case: Falls back to runtime execution (slower but works)


Cache Key Collision:
│
├─ Hash collision probability: ~1 in 2^64 (extremely rare)
│
└─ If collision occurs:
   ├─ Image exists with different content
   ├─ Task may behave unexpectedly
   └─ User can manually clean cache: "Clean cached images" button


Disk Space Management:
│
├─ Each image: ~500MB - 2GB
│
├─ Multiple environments: N × image_size
│
└─ Cleanup strategy:
   ├─ Manual: "Clean cached images" button
   ├─ Auto: Docker's built-in `docker system prune`
   └─ Selective: `docker rmi agent-runner-*:old-key`
```

---

**END OF DIAGRAMS**
