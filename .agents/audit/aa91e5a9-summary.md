# Desktop Cache Implementation - Quick Summary

**Audit ID:** aa91e5a9  
**Full Report:** `aa91e5a9-desktop-cache-implementation.audit.md`

---

## TL;DR

Implement per-environment toggle to pre-build Docker images with desktop components installed, reducing task startup time from 45-90 seconds to 2-5 seconds.

**Overall Risk:** MEDIUM  
**Time Estimate:** 21-30 hours  
**Recommendation:** PROCEED

---

## Files to Modify

### New Files (1)
1. `agents_runner/docker/image_builder.py` (~300 lines)
   - Cache key computation
   - Docker image building
   - Image inspection utilities

### Modified Files (6)
1. `agents_runner/environments/model.py` - Add `cache_desktop_build: bool = False`
2. `agents_runner/environments/serialize.py` - Serialize/deserialize new field
3. `agents_runner/docker/config.py` - Add `desktop_cache_enabled: bool = False`
4. `agents_runner/ui/pages/environments.py` - Add checkbox in General tab
5. `agents_runner/docker/agent_worker.py` - Integrate image builder, conditional preflight
6. `agents_runner/ui/main_window_tasks_agent.py` - Pass setting to config

---

## Implementation Phases

1. **Data Model** (2-3h) - Add fields to Environment and DockerRunnerConfig
2. **UI** (3-4h) - Add checkbox, wire up enable/disable logic
3. **Image Builder** (6-8h) - NEW module for building/caching images
4. **Docker Integration** (4-6h) - Integrate builder into agent_worker
5. **Config Plumbing** (2-3h) - Pass settings through task creation
6. **Testing** (4-6h) - Comprehensive manual testing

**Total:** 21-30 hours

---

## Cache Key Strategy

```
emerald-<base_digest>-<install_hash>-<setup_hash>-<dockerfile_hash>
```

**Components:**
- Base image digest (from `docker inspect`)
- SHA256 of `desktop_install.sh`
- SHA256 of `desktop_setup.sh`
- SHA256 of Dockerfile template

**Automatic rebuild** when any component changes.

---

## Key Design Decisions

1. **Per-environment toggle** (not global) - More flexible
2. **Automatic cache invalidation** via cache key (no manual rebuild button)
3. **Graceful fallback** to runtime install if build fails
4. **Opt-in feature** - Default OFF, backward compatible
5. **Clear logging** - Users see cache hit/miss/build status

---

## Performance Impact

**Without cache:**
- Desktop setup: 45-90 seconds per task

**With cache (hit):**
- Desktop startup: 2-5 seconds per task
- Improvement: 40-85 seconds saved

**With cache (miss):**
- One-time build: 5-10 minutes
- Subsequent runs: 2-5 seconds

---

## Risk Mitigation

1. Always fall back to runtime install on build failure
2. 10-minute timeout on Docker build
3. No changes to default behavior (feature is opt-in)
4. Comprehensive error handling and logging
5. Thorough testing before deployment

---

## Next Steps

1. Review full audit report: `aa91e5a9-desktop-cache-implementation.audit.md`
2. Approve implementation plan
3. Begin Phase 1 (Data Model)
4. Proceed through phases sequentially
5. Test thoroughly after each phase

---

**For detailed implementation guidance, code examples, and testing checklist, see the full audit report.**
