# Bug: GH-managed "Run Agent" shows no immediate feedback

## Summary
On the **New Task** page, clicking **Run Agent** in a GitHub-managed environment can appear to do nothing while the repo is being cloned/branched. The task exists and cloning logs may be emitted, but the UI stays on the New Task page, so the user cannot see the task or its logs until later.

If the user manually navigates to the task viewer during cloning and is watching the clone step, completing the clone can forcibly navigate them back to the dashboard (“kicking them out” of the current view).

## Expected
- As soon as the user clicks **Run Agent**, the app should navigate to a view where progress is visible (dashboard and/or task details), and the task should visibly enter `cloning` immediately.
- Completing the clone/branch prep should not forcibly navigate away from whatever view the user is currently using.

## Notes / Ideas
- Root cause: GH prep path returns early before calling `_show_dashboard()`, so dashboard/info updates remain hidden until GH prep completes.
- The GH prep subprocesses use `capture_output=True`, so a blocked git operation produces no streaming output; log explicit “starting clone/branch prep” lines and consider basic lock detection for `.git/index.lock`.
- Consider running GH prep as a visible “preflight” stage (before Docker pull/run) so it behaves like other preflight work.
