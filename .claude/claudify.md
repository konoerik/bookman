<!-- This project uses claudify — a Claude Code configuration kit.
     Commands: /continue, /save, /log, /prep, /pulse
     To update kit files: /claudify update
     Learn more: https://github.com/konoerik/claudify -->

## Context Loading

Read on every session:
- `docs/CONTEXT.md` — current focus, last decisions, next action

Read when the user mentions tasks, features, bugs, or current work:
- `docs/PLAN.md` — `## Active` section only

Read when writing or editing code:
- `docs/CONVENTIONS.md` — canonical style reference; pattern-match before writing

Read when touching code structure, architecture, or making structural decisions:
- `docs/ARCHITECTURE.md` — `## Quick Reference` first; full file only if needed

Load only when explicitly asked about goals or priorities:
- `docs/ROADMAP.md`

Never auto-load:
- `.claude/archive/`

## Behavior Rules
- For new public functions/modules: write the stub first — signature, the documented contract (expected behavior and failure modes), and a list of named/unimplemented test cases, with no bodies and no implementation. This is a language-agnostic mechanism, not a Python-specific one: what the contract and test-case list actually look like is defined per project in `## Stub` in `docs/CONVENTIONS.md` (e.g. docstring + `Raises` + named pytest functions for exception-based languages, doc comments + returned-error conditions + a table-driven test skeleton for Go, JSDoc + `@throws` for JS) — use that shape, not any other language's, and if this project has no `## Stub` section yet, ask before inventing one. Once the stub is written, pause for review before writing tests or implementation. Skip this for routine one-line fixes and other single-step edits. Critique must come from a fresh context — not the same session that authored the stub — to be worth anything
- Prefer editing existing files over creating new ones
- Maintain a `Makefile` at the project root mirroring the commands in CLAUDE.md `## Development Workflow` (`make test`, `make lint`, `make run`, …) — create it if missing, update it whenever those commands change, so anything run in a session can also be triggered manually
- Do not create `BACKLOG.md`, `TASKS.md`, `TODO.md`, or similar — use `PLAN.md`
- When making an architectural decision, record it with `/log` before ending the session
- Keep `PLAN.md ## Active` short — if it exceeds 10 items, triage before adding more
- Never commit or push without explicit instruction — `/save` and `/prep` are the checkpoints before that happens

## Add-ons
<!-- claudify:addons:start -->
<!-- claudify:addons:end -->
