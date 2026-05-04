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

**ShortStack** is an AI short-video pipeline for the brand **Trending Tech**: pick trends → write script (Sonnet 4.6) → generate visuals + voiceover + captions → render 9:16 mp4 → optional auto-approve gate → upload to YouTube Shorts (or fan out via Buffer to IG/TikTok/X/LinkedIn) → pull metrics → feed top-performer learnings back into the script prompt. **All 9 kickoff phases are done and pushed.** A daily cron produces N videos per niche per day, an auto-approve heuristic gates publishing, and the human-review queue is reserved for new niches or flop streaks. Open work is non-blocking polish (live Buffer-shape verification, ffmpeg loudness, dashboard surfacing of held-for-review reasons).

---

## Repo + branch

| Item | Value |
|---|---|
| Sandbox repo (where Claude works) | `https://github.com/anandka2000/week6` |
| Sandbox branch | `claude/shortstack-mvp-plan-CCjGq` |
| Mirror repo (canonical) | `https://github.com/anandka2000/videogen` (mapped to `main`) |
| Latest commit on sandbox branch | `6bfc7a8` Phase 9 shipped, plus a follow-up fixer commit covering QA9 critical (`include=` registration), pre-loop trends try/except, CLI hardening, cross-field settings validator, and the docs sweep this snapshot tracks |
| Local clone path on user's laptop | `/Users/anaagarw/shortstack` (Mac); planning a fresh Linux box too |

**Sandbox cannot push to videogen** — local proxy is hard-restricted to week6. The user mirrors from their laptop:

```bash
# One-time setup of the second remote in the videogen clone:
cd /Users/anaagarw/shortstack
git remote add week6 https://github.com/anandka2000/week6.git

# Mirror after each Claude session:
alias mirror-shortstack='cd /Users/anaagarw/shortstack && \
  git fetch week6 && \
  git checkout main && \
  git merge --ff-only week6/claude/shortstack-mvp-plan-CCjGq && \
  git push origin main'
```

---

## Commit log on this branch (newest first)

| Commit | What landed |
|---|---|
| (this) | fix: QA9 follow-ups — `include=` registers automation + analytics, pre-loop trends try/except, CLI `--max`/`--platform`/`--visibility` validation, settings cross-field validator, README/USER_GUIDE/DECISIONS Phase-9 docs sweep |
| `6bfc7a8` | Phase 9 — auto-approve heuristic + `daily_pipeline` + `publish_approved` + beat schedule |
| `991d3df` | fix: QA1 + QA2 findings (CLI hardening, StoryIn whitespace, dashboard 422 parsing) |
| `33c50e2` | Phase 8 — user-story mode (`POST /videos/from-story` + dashboard /stories) |
| `413e6cb` | Phase 7 — `BufferPublisher` + `publish_video_all` multi-platform fan-out |
| `e8ae68f` | docs: PROJECT_STATUS.md session-handoff snapshot |
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

---

## Pipeline as of `90fed41`

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

- **162 tests pass** (`uv run pytest` — pure unit tests, no DB or network).
- All `.py` parses cleanly via `ast`.
- TypeScript: `apps/render` and `apps/dashboard` both `tsc --noEmit` clean.
- Phase 7 + Phase 8 audited by parallel QA agents (7/10 + 8/10 confidence); fixer pass shipped (`991d3df`).
- All 9 kickoff phases delivered. Pipeline closes the feedback loop end-to-end.

---

## Local dev setup status (user's side)

The user is setting up two machines:

### Mac (`/Users/anaagarw/shortstack`)
- **Stuck point:** initial Node 25 → pnpm 11 → `node:sqlite` error.
- **Resolution:** install Node 22 LTS (`brew install node@22 && brew link --overwrite --force node@22`). pnpm 11 needs Node 22+.
- **Status as of last conversation:** unverified whether `make install` succeeded after the Node 22 swap.

### Linux box (planned: Core i5 + 16GB)
- **Recommended distro:** Ubuntu 24.04 LTS Desktop (best Docker support, LTS until 2029, 16GB is plenty).
- **Lighter alternative:** Linux Mint 22 (Cinnamon).
- **Setup script** (full quickstart in last message):
  ```bash
  curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER
  curl -LsSf https://astral.sh/uv/install.sh | sh
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
  sudo corepack enable && corepack prepare pnpm@latest --activate
  ```
- **Hardware notes:** 16GB easily fits postgres + redis + minio + worker + Chromium (Remotion). SSD strongly recommended over HDD.

---

## Conventions every future Claude session must follow

(Already in `CLAUDE.md` — repeating the highlights so they're prominent here.)

1. **Doc-update rule:** every feature commit must touch `docs/USER_GUIDE.md`, the README phase table, append to `DECISIONS.md`, and tick `TODO.md`. **A commit that changes user-visible behavior without updating `docs/USER_GUIDE.md` is incomplete.**
2. **Branching:** all work on `claude/shortstack-mvp-plan-CCjGq`. Never force-push, never push to `main`.
3. **Commit messages:** lowercase, conventional prefix (`feat(phase-N): ...`, `fix: ...`, `docs: ...`, `chore: ...`). Body explains *why* and lists notable file changes. **Never include AI attribution lines.**
4. **Tasks take IDs (never payloads), are idempotent, route to the queue named in `workers/shortstack_worker/queues.py`.**
5. **Cost rule:** every cost-incurring producer calls `record_*(...)` then `check_video_cap(session, ...)` in the **same transaction**.
6. **Tests are pure** (respx for HTTP, mock at import boundary). DB-integration tests are deferred until we have a test postgres fixture.
7. **Don't restore deleted helpers without checking why they were removed.**
8. **Don't add features beyond what's asked.** Bugs get fixed, not refactored around.

---

## What I should do next

The 9 kickoff phases are done. The natural next steps are non-blocking polish work tracked in `TODO.md`:

- **Live Buffer API verification** — every endpoint shape is documented as an assumption in `DECISIONS.md`. First real upload will surface mismatches; reconcile then.
- **YouTube Analytics API** — the schema reserves `avg_view_duration_sec`, `retention_curve`, `ctr` columns; only the Data API counts are populated today.
- **ffmpeg LUFS check** in `should_auto_approve` — currently caption coverage is the proxy.
- **Dashboard surfacing of `failure_reason="auto_review: ..."`** so operators see the gate's reasons inline at `/review`.
- **Per-niche threshold overrides** — env-level defaults work for v0; persona-level overrides come when niches drift apart in length/style.

If the operator wants new functionality, common asks would be: A/B testing per niche, multi-template render variants, music tracks under voiceover, billing / quota dashboard, accounts/auth on the dashboard.

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

### Infra
- CI: pytest + ruff + tsc on PR
- Decide MinIO → Cloudflare R2 cutover
- Postgres backup strategy

---

## How to use this file in a new conversation

1. Open a fresh Claude Code session in the repo.
2. Start the conversation by saying: *"Read `docs/PROJECT_STATUS.md` and `CLAUDE.md`, then I want to do X."*
3. Claude will know:
   - Where it is in the project
   - What conventions to follow
   - What was just shipped and what's next
   - Where to push (and where it can't)
   - Which docs to keep current

When the new session ships work, **it must update this file** (commit-log table, phase status, "what I should do next" pointer) as part of the same commit.
