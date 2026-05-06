# PROJECT_STATUS — ShortStack

> **Read this first when starting a fresh Claude Code session.** It's the snapshot that lets a new conversation pick up cleanly. Update it at the end of every working session.
>
> **Companion files** (also in this repo):
> - `CLAUDE.md` — conventions every future session must follow (auto-loaded)
> - `docs/USER_GUIDE.md` — operator + developer reference (settings, CLI, troubleshooting)
> - `DECISIONS.md` — every non-obvious tradeoff with the date it was made
> - `TODO.md` — live punch-list

---

## TL;DR (read this paragraph first)

**ShortStack** is an AI short-video pipeline for the brand **Trending Tech**: pick trends → write script (Sonnet 4.6) → generate visuals + voiceover + captions → render 9:16 mp4 → optional auto-approve gate → upload to YouTube Shorts (or fan out via Buffer to IG/TikTok/X/LinkedIn) → pull metrics → feed top-performer learnings back into the script prompt. **All 9 kickoff phases are done and pushed (HEAD = `33c38d5`).** A daily cron produces N videos per niche per day, an auto-approve heuristic gates publishing, and the human-review queue is reserved for new niches or flop streaks. **There's also a one-shot installer (`make setup` → `scripts/setup.sh`) that handles macOS + Ubuntu/Debian.** Recent work has been a long tail of setup-time fixes from real-machine debugging (Ubuntu Core i5 box) — every problem is either fixed in code or documented below as a known operator gotcha. The user is currently in the middle of a `make e2e-stub` run on Ubuntu; cluster step now produces real Haiku scores after the latest commit (`33c38d5`).

---

## Repo + branch

| Item | Value |
|---|---|
| Sandbox repo (where Claude works) | `https://github.com/anandka2000/week6` |
| Sandbox branch | `claude/shortstack-mvp-plan-CCjGq` |
| Mirror repo (canonical) | `https://github.com/anandka2000/videogen` (mapped to `main`) |
| Latest commit on sandbox branch | `33c38d5` (cluster max-tokens + tighter prompt) |
| Test count | 166 passing |
| Local clones | macOS: `/Users/anaagarw/shortstack`; Ubuntu: `~/shortstack` (active dev box) |

**Sandbox cannot push to videogen** — local proxy is hard-restricted to week6. The user mirrors from their laptop. The recommended alias (handles both remotes + auto-discards regenerated lockfiles):

```bash
alias mirror-shortstack='cd /Users/anaagarw/shortstack && \
  git fetch --all && \
  git checkout main && \
  git checkout -- uv.lock pnpm-lock.yaml 2>/dev/null; \
  git merge --ff-only week6/claude/shortstack-mvp-plan-CCjGq && \
  git push origin main'
```

Equivalent for the Ubuntu box at `~/shortstack`.

---

## Commit log on this branch (newest first)

| Commit | What landed |
|---|---|
| `33c38d5` | cluster task: bigger token budget (4096), tighter prompt (≤12-word rationale, no fences), input cap (50 newest trends) |
| `69ef902` | extract_json salvages prose-wrapped JSON; cluster surfaces raw response on parse failure |
| `cae941f` | e2e_stub reads keys via Settings, not os.environ (the .env wasn't being seen) |
| `4ae875d` | get_niche_by_slug query param renamed `slug` → `niche` (matches dashboard URL convention) |
| `5d78ac7` | alembic.ini paths use `%(here)s` so they're CWD-independent |
| `8824013` | pyproject.toml — root depends on every workspace member explicitly (so `uv sync` actually installs them) |
| `fff5896` | Makefile — run alembic from repo root, not from `infra/` |
| `437b331` | setup.sh — pin to self-contained pnpm 9 binary when `@pnpm/exe` is unreachable |
| `1668c83` | setup.sh — disable corepack before brew/npm install pnpm |
| `5e6e667` | Makefile + setup.sh auto-detect docker compose v2 plugin vs `docker-compose` v1 standalone |
| `9e1eace` | setup.sh + Makefile compose compatibility (drop `--env-file`) |
| `2066534` | **`scripts/setup.sh` — one-shot installer for any new machine** |
| `814daf1` | QA9 follow-ups: include= registers automation+analytics, pre-loop trends try/except, CLI `--max`/`--platform`/`--visibility` validation, settings cross-field validator |
| `6bfc7a8` | **Phase 9 — auto-approve heuristic + `daily_pipeline` + `publish_approved` + beat schedule** |
| `991d3df` | fix: QA1 + QA2 findings (CLI hardening, StoryIn whitespace, dashboard 422 parsing) |
| `33c50e2` | **Phase 8 — user-story mode** (`POST /videos/from-story` + dashboard /stories) |
| `413e6cb` | **Phase 7 — `BufferPublisher` + `publish_video_all` multi-platform fan-out** |
| `e8ae68f` | docs: PROJECT_STATUS.md initial session-handoff snapshot |
| `90fed41` | Phase 6 — snapshots + weekly learnings + dashboard `/metrics` |
| `51ebafe` | Phase 5 — `YouTubeShortsPublisher` + `publish_video` worker task |
| `b2cbac0` | Phase 4 — Remotion `Vertical` composition + `render_video` task |
| `b71c20c` | fix: tester-finding follow-ups (smells + docs) |
| `227898b` | fix: tester findings — negative-cost cache bug, pytest collection, FLUX_MODEL, +4 minor |
| `52857c2` | docs: `USER_GUIDE.md` + `CLAUDE.md` |
| `068d75c` | Phase 3 — visuals slice + `generate_assets` orchestrator |
| `6cabada` | Phase 3 — TTS + captions slices |
| `2200c9e` | Phase 3 prep — S3 storage layer + rolling cost cap helper |
| `e752a19` | Phase 2 — Sonnet script gen with reprompt loop |
| `58f3b08` | Day 7 — polished README + DECISIONS appendix |
| `6bdf951` | Day 6 — approval gate + `make e2e-stub` |
| `38f39e0` | Day 5 — read-only dashboard + API endpoints |
| `9f1916a` | Day 4 — Reddit trends fetch + Haiku clustering + CLI |
| `a1c4265` | Day 3 — Celery app + cost helpers + structlog |
| `36c3beb` | Day 2 — Pydantic schemas + SQLAlchemy models + alembic |
| `4376aa3` | Day 1 — monorepo scaffold |

---

## Phase status

| Phase | Status | Notes |
|---|---|---|
| Day 1: Skeleton | ✅ | docker-compose, all 3 services boot |
| Day 2: Schemas + DB | ✅ | 8 tables, alembic 0001 |
| Day 3: Celery + cost | ✅ | 6 queues, pricing table, structlog, rolling cap |
| Day 4: Trends (Reddit) | ✅ | YouTube + GTrends sources still in TODO |
| Day 5: Dashboard | ✅ | Read-only Next.js pages |
| Day 6: Approval gate | ✅ | `/videos/{id}/{approve,reject}` + `/review` page |
| Day 7: Polish | ✅ | docs |
| **Phase 2: Script gen** | ✅ | Sonnet 4.6, reprompt loop, scene-0 hook constraint, CTA rewrite |
| **Phase 3: Assets** | ✅ | Pexels-first / Flux-fallback (Haiku grader), ElevenLabs Turbo, faster-whisper, rolling cap |
| **Phase 4: Render** | ✅ | Remotion Vertical 1080×1920, Ken Burns, word-level captions, fade-in CTA, mp4 → S3 |
| **Phase 5: Publisher** | ✅ | YouTube Shorts via OAuth refresh-token + resumable upload |
| **Phase 6: Analytics + feedback** | ✅ | `snapshot_metrics` (t+24h/72h/7d), `weekly_learnings` Sonnet → S3, script-gen loads it on next run |
| **Phase 7: Multi-platform** | ✅ | `BufferPublisher` + `publish_video_all` sequential fan-out for IG/TikTok/X/LinkedIn |
| **Phase 8: User-story mode** | ✅ | `POST /videos/from-story` (sync) + dashboard `/stories` page |
| **Phase 9: Full automation** | ✅ | `should_auto_approve` heuristic in render_video + `daily_pipeline_all` + `publish_approved_all` beat schedule |
| **Setup automation** | ✅ | `make setup` / `scripts/setup.sh` for any new mac/ubuntu/debian box |

---

## Pipeline as of `33c38d5`

```
trends → cluster → pick → script (uses learnings.md) → assets → render → APPROVE → publish → snapshots → weekly_learnings ──┐
                            ↑                                                                                                │
                            └────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                          (closed feedback loop)
```

Status transitions on `videos.status`:

```
pending_assets → pending_render → pending_review → APPROVE → approved → publishing → published
                                                  ↘ REJECT ↘
                                                            failed (failure_reason set)
```

---

## What's already running cleanly

- **166 tests pass** (`uv run pytest -q` — pure unit tests, no DB or network).
- All `.py` parses cleanly via `ast`.
- TypeScript: `apps/render` and `apps/dashboard` both `tsc --noEmit` clean.
- Phase 7 + Phase 8 audited by parallel QA agents (7/10 + 8/10 confidence); fixer pass shipped (`991d3df`).
- Phase 9 audited by QA agent (5/10 — found a critical `include=` regression that masked under unit tests; fixed in `814daf1` and now caught by a new regression test that uses `app.loader.import_default_modules()`).
- All 9 kickoff phases delivered. Pipeline closes the feedback loop end-to-end.
- **`make setup` boots a fresh machine end-to-end** — installs missing prerequisites, brings up the docker stack, applies migrations, seeds the niche, runs the test suite. Tested-in-anger on macOS (Apple Silicon) and Ubuntu 24.04. Each setup-time gotcha that surfaced is in code now (see "Setup-time gotchas" below).

---

## Local dev setup status (user's side)

### macOS (`/Users/anaagarw/shortstack`)
- Initial blockers (Node 25 → pnpm 11 `node:sqlite` mismatch, Corepack fetch failure, `@pnpm/exe` URL blocked by corp WAF, brew-installed pnpm SSL cert validation failures) ALL surfaced and fixed in setup.sh.
- **Last known issue:** SSL cert verification failure on `curl https://registry.npmjs.org/`. Cause is environmental (corporate MITM proxy / network filtering) not the code. Recipe is in `DECISIONS.md` and the user's laptop notes — install corp root CA into system trust + set `NODE_EXTRA_CA_CERTS` / `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE`.

### Ubuntu Core i5 + 16GB (`~/shortstack`) — **active dev box**
- Setup completed end-to-end via `make setup` after fixing the npmjs reachability (likely via the pnpm-9 binary fallback).
- `make e2e-stub` is **partway working**:
  - ✅ Reddit trend fetch (4 subreddits, 100 trends written)
  - ✅ Haiku cluster step (after `33c38d5`'s max_tokens + prompt fix; previously hit max_tokens=2048 mid-stream and produced unparseable truncated JSON)
  - 🔜 unverified: Sonnet script gen, asset generation, render, publish (depends on which keys are in `.env` + niche `voice_id` set to a real ElevenLabs voice)
- The user has at least `ANTHROPIC_API_KEY` configured in `.env`. Status of the other keys (ELEVENLABS, PEXELS, REPLICATE, YOUTUBE_OAUTH_*, BUFFER) and the niche `voice_id` is not yet confirmed.

---

## Setup-time gotchas (debugged in real time, all fixed in code)

These are the issues the user actually hit during fresh-machine setup. Each has a commit fix or an operator workaround. Future sessions / new machines should not see these unless something regresses.

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | `node:sqlite` ERR_UNKNOWN_BUILTIN_MODULE on `pnpm install` | Node 20 too old; pnpm 11 needs Node 22.13+ | `setup.sh` installs Node 22 LTS specifically. |
| 2 | `unknown flag: --env-file` from `make up` | Old / non-Docker-Desktop compose plugin doesn't accept the flag | Dropped `--env-file` in Makefile (`9e1eace`); the compose file uses `${VAR:-default}` everywhere so .env override isn't needed. |
| 3 | "Docker Compose plugin v2 missing" on Colima/Podman/older Docker | Setup script + Makefile only checked for `docker compose` (v2 plugin) | Auto-detect `docker compose` vs `docker-compose` (`5e6e667`). |
| 4 | `corepack prepare pnpm@latest --activate` fetch failure | Corepack must hit `registry.npmjs.org` for pnpm bootstrap | setup.sh now: try Corepack → fall back to brew/npm → fall back to direct GitHub-released pnpm 9 binary (`437b331`). |
| 5 | brew refuses to symlink `/opt/homebrew/bin/pnpm` over Corepack shim | Corepack created its own shim before brew tried to install | setup.sh runs `corepack disable` before brew install (`1668c83`). |
| 6 | `@pnpm/exe` fetch fails (`registry.npmjs.org/@pnpm%2Fexe` returns 4xx) on corp Wi-Fi or hotel captive portals | pnpm 10+ split runtime executable into a separately-fetched npm package; URL with `%2F` triggers WAF rejection on some networks | Fall back to pnpm 9 binary which has no runtime fetch (`437b331`). |
| 7 | `curl: (60) SSL certificate problem: unable to get local issuer certificate` | Corp / VPN / public-Wi-Fi MITM proxy re-signs HTTPS with a CA the system doesn't trust | Operator action — install corp CA into system trust + set `NODE_EXTRA_CA_CERTS`, `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`. Or use a clean network. Documented in DECISIONS. |
| 8 | `Failed to spawn: alembic` from `make migrate` | uv project discovery from `infra/` subdir didn't find the root workspace .venv | Run alembic from repo root with `-c infra/alembic.ini` (`fff5896`). |
| 9 | `Path doesn't exist: migrations` from alembic | alembic resolves `script_location` relative to CWD, not to `.ini` directory | `alembic.ini` paths use `%(here)s` template so they're CWD-independent (`5d78ac7`). |
| 10 | `ModuleNotFoundError: No module named 'shortstack_worker'` from pytest | Root `pyproject.toml` had workspace members declared but didn't depend on them, so `uv sync` only installed transitively-pulled-in members | Root project now explicitly depends on all 4 workspace members (`8824013`). |
| 11 | `/review` shows "Failed to load: GET /videos -> 422" | `get_niche_by_slug(slug: str, ...)` expected `?slug=...` but dashboard sent `?niche=...` | Renamed dependency parameter `slug` → `niche` (`4ae875d`). Affected `/trends`, `/videos`, `/metrics`, `/costs/daily` too — all silently empty before the fix. |
| 12 | `make e2e-stub` says "ANTHROPIC_API_KEY missing" even after editing `.env` | Script used `os.environ.get(...)` but `.env` is loaded only by `pydantic-settings` into the `Settings` object | Switched to `get_settings()` (`cae941f`). All other code already used Settings; e2e_stub was the odd one out. |
| 13 | cluster step fails with `Expecting value: line 1 column 1 (char 0)` then with `no parseable JSON` | Haiku response truncated mid-JSON because output hit `max_tokens=2048` (Haiku wrote verbose 50-word rationales for 100 trends) | Bigger budget (4096), input cap (50 newest), prompt: rationale ≤12 words + no `\`\`\`json` fences (`33c38d5`). Plus extract_json now salvages prose-wrapped + unclosed-fence cases (`69ef902`). |

---

## Conventions every future Claude session must follow

(Already in `CLAUDE.md` — repeating the highlights so they're prominent here.)

1. **Doc-update rule:** every feature commit must touch `docs/USER_GUIDE.md`, `docs/PROJECT_STATUS.md`, the README phase table, append to `DECISIONS.md`, and tick `TODO.md`. **A commit that changes user-visible behavior without updating `docs/USER_GUIDE.md` + `docs/PROJECT_STATUS.md` is incomplete.**
2. **Branching:** all work on `claude/shortstack-mvp-plan-CCjGq`. Never force-push, never push to `main`.
3. **Commit messages:** lowercase, conventional prefix (`feat(phase-N): ...`, `fix: ...`, `docs: ...`, `chore: ...`). Body explains *why* and lists notable file changes. **Never include AI attribution lines.**
4. **Tasks take IDs (never payloads), are idempotent, route to the queue named in `workers/shortstack_worker/queues.py`.**
5. **Cost rule:** every cost-incurring producer calls `record_*(...)` then `check_video_cap(session, ...)` in the **same transaction**.
6. **Tests are pure** (respx for HTTP, mock at import boundary). DB-integration tests are deferred until we have a test postgres fixture.
7. **API keys are read via `shortstack_core.settings.get_settings()`** — never via `os.environ` directly. `.env` is loaded by pydantic-settings, not by Python.
8. **Don't restore deleted helpers without checking why they were removed.**
9. **Don't add features beyond what's asked.** Bugs get fixed, not refactored around.

---

## What I should do next

**The 9 kickoff phases are done.** The user is currently driving `make e2e-stub` end-to-end on Ubuntu. Next likely interactions:

### Near-term (this session or imminent next session)
- Confirm `make e2e-stub` runs all the way through Sonnet script gen with the cluster fix from `33c38d5`. If the cluster step still has issues, the error message now includes the raw Haiku response — we can iterate from there.
- Walk the user through adding ElevenLabs / Pexels / Replicate keys + setting the niche `voice_id`, then run `make e2e-stub` end-to-end to render a real mp4.
- Walk through `make publish VIDEO=<uuid>` once they have YouTube OAuth set up.

### Medium-term polish (in `TODO.md`, none blocking)
- **Live Buffer API verification** — every endpoint shape is documented as an assumption in `DECISIONS.md`. First real upload will surface mismatches; reconcile then.
- **YouTube Analytics API** — the schema reserves `avg_view_duration_sec`, `retention_curve`, `ctr` columns; only the Data API counts are populated today.
- **ffmpeg LUFS check** in `should_auto_approve` — currently caption coverage is the proxy.
- **Dashboard surfacing of `failure_reason="auto_review: ..."`** so operators see the gate's reasons inline at `/review`.
- **Per-niche threshold overrides** — env-level defaults work for v0; persona-level overrides come when niches drift apart in length/style.

### Big asks the operator might raise next
A/B testing per niche, multi-template render variants, music tracks under voiceover, billing / quota dashboard, accounts/auth on the dashboard, cluster batching to handle >50 trends per niche per day.

**Plan-then-execute pattern:** propose the plan in 1–2 paragraphs, list 2–3 design questions, wait for "go", then ship in one commit and update this file.

---

## Live open questions / TODOs (full list in `TODO.md`)

### Phase 6 leftovers (defer; nice-to-have)
- YouTube **Analytics API** for `avg_view_duration_sec`, `retention_curve`, `ctr` (Data API only exposes counts)
- Sonnet **Batch API** for the weekly learnings synthesis (50% off, 24h SLA — fine for weekly cadence)
- Surface `learnings.md` content on the dashboard

### Phase 4 leftovers
- Tune `RENDER_COST_PER_SEC_USD` once we know the prod box

### Phase 3 leftovers
- Asset reuse cache keyed by `sha1(visual_prompt + style)` per niche (would zero out repeat-image spend)
- Surface soft-cap warning on the video row (currently structlog only)

### Schema follow-up
- Promote `Video.cost_cents` to `Numeric` via a new alembic migration (currently rounded `Integer`; sub-cent precision IS preserved on `cost_events.cost_cents`).

### Day 4 leftovers
- YouTube Data API source + Google Trends source
- PRAW migration for Reddit (currently public `/hot.json`)
- **Cluster batching:** if a niche pulls >50 trends, only the newest 50 get scored per `cluster()` call. Older ones get scored on subsequent calls (idempotent), but for high-volume niches this wastes a Haiku call. Could batch in a loop within one `cluster()` invocation.

### Operator UX
- Make `make e2e-stub` accept a `--dry-run` flag that prints the planned steps without executing.
- Document the npmjs `%2F` MITM/firewall scenario more visibly in `docs/USER_GUIDE.md` troubleshooting (currently in `DECISIONS.md` only).

### Infra
- CI: pytest + ruff + tsc on PR (the test suite is fast — 166 tests in ~3s).
- Decide MinIO → Cloudflare R2 cutover.
- Postgres backup strategy.

---

## How to use this file in a new conversation

1. Open a fresh Claude Code session in the repo (`week6` if working on the sandbox, `videogen` if mirroring locally).
2. Start the conversation by saying: *"Read `docs/PROJECT_STATUS.md` and `CLAUDE.md`, then I want to do X."*
3. Claude will know:
   - Where it is in the project (latest commit, what's been delivered)
   - What conventions to follow (doc-update rule, branch policy, commit style)
   - What the user's local box state is (Mac SSL/MITM issue, Ubuntu mid-e2e-stub debug)
   - What was just shipped and what's next
   - Where to push (sandbox week6) and where it can't (videogen directly)
   - Which docs to keep current

When the new session ships work, **it must update this file** (commit-log table, phase status, "what I should do next" pointer) as part of the same commit. The `CLAUDE.md` rule is binding: a commit that changes user-visible behavior without updating `PROJECT_STATUS.md` + `USER_GUIDE.md` is incomplete.
