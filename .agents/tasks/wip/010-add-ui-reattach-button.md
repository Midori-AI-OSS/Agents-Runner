# Task 010: Add UI Reattach Button for Running Interactive Tasks

## Objective
Add a UI affordance (button or menu item) that allows users to reattach to a running interactive container.

## Context
- After app restart, interactive containers may still be running
- Users need an easy way to reattach without manually running attach command
- Button should open a terminal with the attach command

## Requirements
1. Add "Attach" or "Reattach" button to task UI for running interactive tasks
2. Button should only be visible when task is interactive and status is "running"
3. Clicking button should open terminal with: `docker attach <container_name>`
4. Should reuse same terminal launcher mechanism as initial launch

## Location to Change
- File: `agents_runner/ui/pages/task_details.py`
- Class: `TaskDetailsPage.__init__` (around lines 83-92)
- Add button similar to `_desktop_btn` (lines 83-87)
- Add to header layout (around line 92)
- Create handler function: `_on_attach_clicked` or `_reattach_to_container`
- Update `_sync_desktop_button` pattern with new `_sync_attach_button` method
- Show button when: `task.status == "running"` and task is interactive type

## Acceptance Criteria
- [ ] "Attach" or "Reattach" button visible for running interactive tasks
- [ ] Button not visible for non-interactive tasks
- [ ] Button not visible for completed/failed tasks
- [ ] Clicking button opens terminal with attach command
- [ ] Terminal successfully attaches to running container
- [ ] Works after app restart

## Notes
- This improves UX after task 006 (recovery reattach support)
- Consider showing container status (running/exited) in UI
- Could also add keyboard shortcut for quick reattach
- Lower priority, implement after core recovery works
