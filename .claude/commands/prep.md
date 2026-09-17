Run a pre-ship checklist before I open a PR or push a release.

Work through each item and report pass/fail/skip with a brief reason:

**Code**
- [ ] All tests pass
- [ ] No leftover debug logs, commented-out code, or TODOs in changed files
- [ ] No hardcoded secrets or environment-specific values — scan for credential patterns (API keys, AWS keys, private-key blocks, bearer tokens, passwords in connection strings) across the full set of pending changes: `git diff` (or `git diff --staged`) for tracked edits, plus the actual contents of every untracked file from `git status --porcelain` (`git diff` alone never shows new-file content). Report any matches with file/line, not just a visual skim

**Docs**
- [ ] docs/PLAN.md ## Active updated — completed items moved to ## Done
- [ ] If an architectural decision was made, it's recorded in docs/ARCHITECTURE.md
- [ ] docs/CONTEXT.md reflects the current state

**Review**
- [ ] Changes are scoped to what was planned — no unrelated modifications
- [ ] Any new dependencies are intentional and noted in docs/ARCHITECTURE.md ## Quick Reference

If any item fails, surface it clearly and ask whether to fix it now or proceed anyway.
