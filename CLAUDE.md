# CLAUDE.md

Project conventions for AI assistants working on this repo. Keep short; this file is read into every session.

> **First action of every new session:** read `docs/PROJECT_STATUS.md`. It's the live snapshot of where the project stands, the latest commit, what shipped most recently, and what's next. It's also the doc you must update when you ship work.

## Doc layout (keep current)

When you ship a feature, update **all** of these in the same commit:

| File | When to touch |
|---|---|
| `docs/USER_GUIDE.md` | Any user-facing change: new CLI command, new make target, new env var, new pipeline step, new dashboard page, changed cost knob, new failure mode |
| `docs/PROJECT_STATUS.md` | Every shipped commit — bump the commit-log table, tick the phase status, point to what's next |
| `README.md` (phase status table only) | When a phase or day is completed |
| `DECISIONS.md` (append a dated section) | When a non-obvious tradeoff is made |
| `TODO.md` | When a TODO item is finished, or a new one is discovered |

If a commit changes user-visible behavior and doesn't touch `docs/USER_GUIDE.md` + `docs/PROJECT_STATUS.md`, the commit is incomplete.

## Branching

- All work goes on `claude/shortstack-mvp-plan-CCjGq` in `anandka2000/week6` (this is the dev sandbox).
- The user mirrors to `anandka2000/videogen` `main` from their laptop after each push.
- Never force-push, never push to `main` directly.

## Commit messages

- One-line title, lowercase, conventional prefix: `feat(phase-N): ...`, `fix: ...`, `docs: ...`, `chore: ...`
- Body explains the *why* and lists notable file changes / interface changes.
- Never include AI attribution lines.

## Code style

- Python 3.11+. Pydantic v2, SQLAlchemy 2.0 typed mappings.
- Tests are pure (respx for HTTP, mock at import boundary). DB-integration tests are deferred until we have a test postgres fixture.
- Cost-incurring producers MUST: `record_*(...)` then `check_video_cap(session, ...)` in the same transaction.
- Tasks take an ID (never a payload), are idempotent, and route to the queue named in `workers/shortstack_worker/queues.py`.
- See `DECISIONS.md` before changing schema, prompt versioning, or cost guardrails.

## Don't

- Don't restore deleted helpers without checking why they were removed.
- Don't add features beyond what's asked. Bugs get fixed, not refactored around.
- Don't skip the docs update.
