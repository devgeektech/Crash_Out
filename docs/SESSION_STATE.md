# CRASH OUT — Session State

Living log of meaningful project changes. Keep this updated as work lands.  
Do **not** treat the JD as a delivery checklist — see [PRODUCT.md](PRODUCT.md).

**Refs:** [JD_RFP_CRASH_OUT.md](JD_RFP_CRASH_OUT.md) (idea) · [ARCHITECTURE.md](ARCHITECTURE.md) · `README.md` · `AGENTS.md`

---

### 2026-11-17 — Pgvector Deduplication, Temporal S3 Automation & UI Polish

Completed:
- **JWT Authentication**: Implemented JSON Web Token (JWT) authentication for login. Tokens are generated upon login and accepted via both `Authorization: Bearer <token>` headers (for API clients) and secure HTTP-only cookies (`crashout_jwt`) for web UI session persistence. Added `POST /api/auth/token` API endpoint for programmatic token generation.
- **LLM Model Upgrade**: Set default OpenAI model to `gpt-6-luna` across `.env`, `.env.example`, `app/config.py`, `app/trends/concept_writer.py`, and `app/trends/friction.py`.
- **Cleaned Mockup & Test Artifacts**: Purged all mock test directories (`ep_mock_test`, test episodes `ep_1794*`, dummy `.mp4` chunks, stale pitch caches) and reset `pipeline_index.json` and `custom_catalog.json` to clean state.
- **Clean Gateway 1 Pitches Page**: Removed redundant "Mock Scheduler" button from Stage 1 (Top Friction Pitches) action bar so the single canonical mock runner lives on the Studio Queue ("Mockup" button).
- **Studio Queue Mockup Scheduler Button**: Replaced manual "Add" dropdown in Stage 0 Studio Queue with a one-click **"Mockup"** button that executes the full daily 06:00 UTC scheduler pipeline (fetches live Layer A/B/C trends, runs clustering, friction scoring, vector deduplication), creates a new video entry in the queue, and immediately loads all 5 generated Pitch Cards in Gateway 1.
- **Free Direct Data Providers ($0 Cost Optimization)**:
  - Google Trends US: Using free Google Trends US RSS feed (`https://trends.google.com/trending/rss?geo=US`).
  - Mainstream US News: Direct free RSS feeds from AP, Reuters, CNN, Fox News, NY Post, Morning Brew, The Verge, and Google News US without requiring SerpApi / SearchApi paid plans.
  - Reddit: Official free Reddit PRAW API and public JSON listing fallback for target subreddits.
  - YouTube: Official YouTube Data API v3 (free tier).
  - Know Your Meme: Official direct RSS feed (`https://knowyourmeme.com/newsfeed.rss`).
- **Docker Compose Stack**: Created `docker-compose.yml` and `docker/init-scripts/01-init.sql` combining PostgreSQL 16 (`pgvector/pgvector:pg16`), Temporal Auto-Setup Server, and Temporal UI.
- **Pgvector Pitch Deduplication**: Enhanced `store.py` and `friction.py` with cosine similarity vector comparison ($\ge 0.82$) preventing duplicate pitches within current batches and against historical runs.
- **06:00 UTC Scheduled Runs**: Configured dual daily schedule via Temporal native schedule (`DailyAgent0Workflow` on `0 6 * * *`) and APScheduler fallback.
- **Temporal S3 Video Sync**: Added `sync_episode_videos_to_s3_activity` to upload rendered scenes and master merged 9:16 videos directly to Amazon S3.
- **UI & Navigation Modernization**:
  - Renamed *Studio* -> *Agent Studio* and *Characters* -> *Characters Library*.
  - Simplified Settings: Removed deprecated *Model* and *Reference model* dropdowns from Vidu settings.
  - Sidebar Layout: Fixed sidebar to left across viewports; converted to 3-line hamburger drawer on screens $\le 980\text{px}$.
  - Episodes Management: Updated table column header from *Production* to *Status*.
  - Typography: Enforced bold headers (`h1`–`h6` & `<th>`) and clean unbolded table body cells (`td`).
- **Developer Guidelines**: Created `AGENTS.md` specifying architecture, patterns, fallback rules, and session logging protocols.

---

### 2026-11-14 — Agent 0 client friction-intersection engine

Completed:
- Layer A/B/C collectors (`sources_a/b/c.py`) with graceful key/RSS fallbacks + web-search soft fill.
- Embedding/Jaccard clustering (`cluster.py`) + weighted LLM/heuristic friction scoring (`friction.py`).
- Top **5** client pitch schema → Gate 1 UI (`stage_1.html`); SENSITIVE_REVIEW requires confirm.
- File + optional Postgres/pgvector store (`store.py`); 30-day episode topic memory on approve.
- APScheduler daily 06:00 America/New_York + Telegram dispatch (env-gated).
- APIs: `POST /api/agent0/run`, `GET /api/agent0/latest`.

---

### 2026-11-13 — Production statuses Draft→Scripting→Generating→Published

Completed:
- Status flow: **Draft** (pre-concept) → **Scripting** (concept OK) → **Generating** (script OK) → **Published** (video OK).
- Published shows move to `/episodes`; dashboard mix/KPIs/active card updated (no Review/Approved).
- Approving video (Gateway 3) publishes and opens the record page.

---

### 2026-11-13 — Code structure cleanup

Completed:
- Removed empty `scripts/`, unused `powershell.cmd`, dead `home.html` / `index.html`.
- Deduped brand art (served from `app/static/assets/brand/` only).
- Moved studio helpers → `app/studio/`; FFmpeg merge → `app/media/merger.py`.
- Added package `__init__.py` files; reference prompts → `docs/reference/prompts/`.
- Updated imports + `ARCHITECTURE.md`.

---

### 2026-11-13 — Episodes = finished library only

Completed:
- `/episodes` lists only shows that cleared all gateways (`COMPLETED` / approved).
- In-progress work stays in Studio; HITL column removed from Episodes.
- Approving Gateway 5 graduates the show into the Episodes list.

---

### 2026-11-13 — Client brand art + theme

Completed:
- Added `crash_out_badge.jpg` (header mark) and `crash_out_family.png` (dashboard hero).
- Rethemed UI accents to neon pink / yellow / cyan from client art.

---

### 2026-11-13 — Studio menu unify + credits (no dollars)

Completed:
- Nav is **Dashboard · Studio · Episodes · Characters** (Queue removed; `/queue` → `/studio`).
- Dashboard/studio usage shows **credits used**, not dollars.
- Removed “Mock (offline)” UI labels — engine badge reads **Vidu Q4**.

---

### 2026-11-13 — Production dashboard + nav menus

Completed:
- Fixed `revision_notes` UndefinedError (safe defaults + always-populated context).
- `/` is now a production **Dashboard** (KPIs, active episode, recent eps, queue peek, notes).
- Top nav menus refined in newer entry above.
- `run.py` reload enabled so template/code changes pick up.  

---

### 2026-11-13 — Audio = Vidu native only (no TTS / lip-sync)

Completed:
- Product decision: **no ElevenLabs, no voice API, no separate lip-sync** — spoken audio is generated by Vidu with the clip (`audio: true`).
- Character “voice” fields are **Vidu audio direction / tags** for prompts, not TTS settings.
- Studio panel reframed; removed misleading post-prod mix/SFX track UI.
- Docs (`PRODUCT`, `ARCHITECTURE`, this file) updated; JD Agents 2–3 marked skipped for POC.

Pending:
- Live Vidu when `VIDEO_ENGINE=vidu` + credits restored  
- Optional: CV-based visual QA later  

Issues: None.  

Next: Keep prompts rich with dialogue + audio tags; generate with Vidu when credits return.

---

### 2026-11-13 — Full studio feature set (19 items, Vidu-safe)

Completed (all roadmap areas, mock engine):
1. Episode management — `/episodes` CRUD/duplicate/number/status  
2. Character library — `/characters` + `library.json`  
3. Script management — per-scene prompt + per-line dialogue edit + script versions restore  
4. Approval workflow — production_status + revision notes  
5. Individual clip regen — mock-safe single-scene generate  
6. Generation queue — waiting/processing/completed/failed + dedupe/retry + background enqueue  
7. Auto assembly — FFmpeg merge + optional intro/outro  
8. Generation history — archive + restore earlier clip versions  
9. Vidu voice tags — tone/pitch/speed/delivery on characters (prompt direction)  
10. Dialogue timing — sync/edit timestamps for Vidu timeline prompts  
11. *(obsolete)* Separate audio mix tracks — dropped; audio baked in Vidu clips  
12–13. Consistency / visual QA — human checklists per scene  
14. Scene continuity — extract last frame via FFmpeg for next clip  
15. Prompt templates — `prompt_templates.json` + apply/combine  
16. Cost tracking — ledger + regenerations summary  
17. Background processing — daemon worker + in-app notifications  
18. Export — per-asset links, ZIP, 16:9 letterbox  
19. Auto-save — title + script prompt debounced HTMX saves  

Pending: see newer entry above.

---

### 2026-11-13 — Phase 1 studio roadmap (Vidu-safe)

Completed: mock engine, episodes dashboard, character library, queue/history skeleton, intro/outro slots.  
Superseded by full feature set entry above.

---

### 2026-11-13 — Agent 0 switched to simple web search

Completed:
- Replaced Reddit/GDELT/NewsAPI/Google Trends stack with **web search** via `ddgs` (no API keys).
- Targeted queries for US culture / Gen Z / HOA / cost-of-living / wellness; filter + heuristic/LLM concept writer + cache/static fallback unchanged.
- Cleaned `.env.example` / config of unused Reddit/News keys; added `ddgs` to `requirements.txt`.

Pending:
- Optional: `OPENAI_API_KEY` for richer concept cards.
- Optional: Telegram HITL / live publish (JD) — not started.

Issues:
- Some search backends return empty; Yahoo backend used first with fallbacks.

Next:
- Continue POC polish; update this file on meaningful changes.

---

### 2026-11-13 — Project docs + Agent 0 live trend ingestion

Completed:
- Saved original RFP/JD to `docs/JD_RFP_CRASH_OUT.md` (reference only).
- Added `docs/PRODUCT.md` (POC scope vs JD), `docs/ARCHITECTURE.md`, and this session file.
- Clarified product rule: continue current Vidu/HITL POC path; JD is idea guidance, not full build scope.
- **Agent 0 live topics (initial):** multi-source ingest — later replaced by web search (see entry above).
- Gate 1 refresh logs concept titles; theme filter + cache/static fallback.

Pending: (see newer entry)  
Issues: (see newer entry)  
Next: (see newer entry)

---

### 2026-11-12 — Manual catalog concept loop + Final_Sample merge

Completed:
- Fixed repeated Gate 1 concept approval for manually added videos: keep mid-pipeline episodes (script / `gateway >= 2`) even without MP4s; catalog reopen resumes Script/Video instead of rewinding to Concept.
- Prefer higher-progress related episodes when scoring duplicates.
- Merged `ep_1794482502_Final_Sample` scenes → `merged_60s.mp4` and updated episode state.

Pending: None for that bug.  
Issues: None.  
Next: Live trend options / Agent 0 (done above).

---

### Earlier POC foundation (pre-session summary)

Completed:
- FastAPI HITL Hub (Jinja + HTMX) with staged gateways.
- Vidu Q4 Preview only (`reference2video` / `img2video`), native audio, 9:16.
- Concurrent 4-scene generation (ThreadPoolExecutor); Windows Proactor disconnect noise silenced.
- Episode-scoped outputs: `outputs/ep_<id>_<Title>/` + per-episode `episode.json` (no monolith state).
- Characters moved to `characters/*_9x16.png` (single variant); `/characters` mount.
- Custom catalog / manual video add path.
- FFmpeg merge to `merged_60s.mp4`.
- Agents 4–5 draft packages (no live publish).
- Removed tombstone `.deleted_episodes.json`; prune empty non-progress episodes via index keep rules.

---

## How to update this file

After each meaningful change set, add a new dated section at the **top** (below the header) with:

- **Completed** — what landed  
- **Pending** — open follow-ups  
- **Issues** — known bugs/risks  
- **Next** — suggested next step  

Keep entries compact; link to files instead of pasting large diffs.
