# Task Management

This directory contains planned, active, and completed tasks for the Agents Runner project.

## Current Active Tasks

### a7f3b291 - Git Task Isolation for Concurrent Operations
**Status:** 📋 Ready for Implementation  
**Priority:** P1 (High)  
**Effort:** 4-6 hours  

**Problem:** Concurrent tasks using GitHub repo mode share a single git directory, causing lock collisions and contamination.

**Solution:** Isolate each task to its own git clone directory.

**Documents:**
- [a7f3b291-index.md](./a7f3b291-index.md) - Start here! Master index
- [a7f3b291-git-task-isolation.md](./a7f3b291-git-task-isolation.md) - Detailed implementation plan
- [a7f3b291-quick-reference.md](./a7f3b291-quick-reference.md) - Quick reference
- [a7f3b291-architecture.md](./a7f3b291-architecture.md) - Architecture diagrams
- [a7f3b291-summary.md](./a7f3b291-summary.md) - Implementation summary

**Next Action:** Assign to Coder Mode for implementation

---

## Task Naming Convention

Tasks use a random 8-character hex prefix for easy reference:

```
{prefix}-{descriptive-name}.md
```

Example: `a7f3b291-git-task-isolation.md`

## Task Lifecycle

```
Planning → Implementation → Testing → Review → Done
```

1. **Planning** - Task Master creates task documents
2. **Implementation** - Coder Mode implements the solution
3. **Testing** - Tester Mode validates functionality
4. **Review** - Reviewer/Auditor Mode checks quality
5. **Done** - Task moved to `done/` directory

## Task Document Types

- **index.md** - Master index and overview
- **{task}.md** - Detailed implementation specification
- **quick-reference.md** - Cheat sheet for implementers
- **architecture.md** - Architecture diagrams and design
- **summary.md** - Implementation roadmap

## Completed Tasks

See `done/` directory for archived tasks.

---

*Last Updated: 2025-01-06*
