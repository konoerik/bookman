Prepare and verify a library release.

Work through each item and report pass/fail/skip with a brief reason:

**Version**
- [ ] Version bumped in `pyproject.toml` (or `setup.cfg`) following semver — patch for fixes, minor for new API, major for breaking changes
- [ ] `CHANGELOG.md` updated with the new version, date, and summary of changes
- [ ] No unreleased changes left under `## Unreleased` that belong in this release

**Code**
- [ ] All tests pass
- [ ] No leftover debug logs, commented-out code, or TODOs in changed files
- [ ] Public API matches what is documented — no surprises in `__all__`

**Docs**
- [ ] docs/PLAN.md ## Active updated — completed items moved to ## Done
- [ ] Any API changes or deprecations recorded in docs/ARCHITECTURE.md
- [ ] docs/CONTEXT.md reflects current state

**Git**
- [ ] Changes committed on main (or release branch)
- [ ] Tag created: `git tag v{version}`
- [ ] Tag pushed: `git push origin v{version}`

If any item fails, surface it clearly and ask whether to fix it now or proceed anyway.
