# CRASH OUT — Session State

Living log of meaningful project changes. Keep this updated as work lands.  
Do **not** treat the JD as a delivery checklist — see [PRODUCT.md](PRODUCT.md).

**Refs:** [JD_RFP_CRASH_OUT.md](JD_RFP_CRASH_OUT.md) (idea) · [ARCHITECTURE.md](ARCHITECTURE.md) · `README.md` · `AGENTS.md`

---

### 2026-11-26 — Sensitive topic confirm uses themed in-app dialog

Completed:
- Replaced native browser `hx-confirm` alert for `SENSITIVE_REVIEW` Approve Pitch with the shared `#app-confirm-dialog` (warn styling + “Approve anyway”).
- All `hx-confirm` prompts now route through `htmx:confirm` → themed dialog (delete stays danger-styled).

Files: `app/static/js/ui.js`, `app/templates/base.html`, `app/static/css/app.css`, pitch modal + stage_1 templates

### 2026-11-26 — Delete episode clears pitch; Work history after Approve only

Completed:
- Deleting an episode clears its research pitch cache so View Pitch / ✓ Pitch Approved does not linger for that signal.
- Pitch modal Approve state is tied to the episode that owns the signal, not an unrelated active shell.
- Work history lists episodes only after **Approve Pitch** (gateway ≥ 2 / script); Create Pitch draft shells stay out.

Files: `app/ui.py`, `app/trends/research_ui.py`

### 2026-11-26 — Regenerate Pitch loading lock + spinner

Completed:
- Clicking **Regenerate Pitch** greys out / disables **Approve Pitch** until the new card returns.
- Pitch card shows a loading overlay spinner while regeneration runs.

### 2026-11-26 — Episode Pitch card fits viewport

Completed:
- Pitch modal capped to ~88vh with a scrollable body; footer (notes / Regenerate / Approve) stays pinned on-screen.

### 2026-11-26 — Approve Pitch: simple Regenerate Pitch control

Completed:
- Episode Pitch modal shows optional notes (`Add notes for Regeneration (Optional)`) + **Regenerate Pitch**, then **Approve Pitch**.
- Notes are optional; regenerating refreshes the card in-place.

### 2026-11-26 — Approve Pitch HITL: regenerate / improve

Completed:
- Episode Pitch modal (while approving) now offers **Regenerate completely** and **Improve with notes**.
- Improve requires human guideline text; both keep the modal open and refresh the pitch card.
- Friction scorer accepts HITL mode + prior pitch + guidance for a full replacement card.

### 2026-11-26 — Fix Windows hang after Temporal worker reload

Completed:
- Root cause: uvicorn `--reload` cancelled the in-process Temporal worker; gRPC threads kept the child alive, so `/login` timed out after `Worker cancelled, shutting down`.
- Dev (`run.py` reload): skip embedded Temporal worker; still connect/register schedules.
- Harder shutdown: call `worker.shutdown()` with timeout; never block lifespan exit more than ~2.5s.
- Watch only `app/` for reload to avoid noisy StatReload loops.

### 2026-11-26 — Pulled master on live (`admin.crashout.tv`)

Completed:
- Fast-forward pulled `origin/master` on EC2 (`54.166.201.137` / `/var/www/Crash_Out`) from `604ee36` → `da23bbc`.
- Restarted `crashout.service`; service active; `/login` returned HTTP 200.

### 2026-11-26 — Remove Trend Signal ⋯ open-source control

Completed:
- Removed the right-side three-dot “Open source” control from the Trend Research detail panel.

### 2026-11-26 — Top 10 ranked by joint score (media × social)

Completed:
- Each topic now scores **cross-media (A) alone**, **social-proof (B) alone**, and a **joint** combined score.
- Today’s top 10 list sorts highest joint score → lowest; list shows joint; detail shows Media / Social / Joint breakdown.
- Single-stream topics are scaled down so true Media × Social hits rise to the top.

### 2026-11-26 — Waiting Pitch Approving opens Trend Research

Completed:
- Work history Open (and `/studio?stage=1`) for **Waiting Pitch Approving** now lands on Today’s Trend Research instead of the pitch-card page.
- Agent M / HITL deep links for Gate 1 point at stage 0.

### 2026-11-26 — Approve Pitch closes card + Generating Script alert

Completed:
- On Approve Pitch, Episode Pitch modal closes immediately and shows **Generating Script…** until Scriptwriter loads.

### 2026-11-26 — Agent bar + Approve Pitch → Scriptwriter

Completed:
- Today's research: A0–A5 stepper stays fully greyed/inactive.
- Work history / pipeline: stepper green for cleared gates, grey for locked, from episode `current_gateway` / status.
- Approve Pitch generates Agent 1 script (same as Gate 1) and opens Scriptwriter UI; Animation & Rendering unchanged.

### 2026-11-26 — Work history Pitch column = View Pitch

Completed:
- Work history tab active pill forced white.
- Pitch column uses eye-icon **View Pitch** button (opens Episode Pitch modal); bulb icon removed.

### 2026-11-26 — Widen Pitch details modal

Completed:
- Pitch details panel stretches to `min(1180px, 96vw)` so it fills the screen horizontally.

### 2026-11-26 — Pitch fields: name / merch / potential / characters / storyline / comedy

Completed:
- AI pitch now generates: Episode name, Merch punchline (= episode name), Episode potential, Character involvement, Possible storyline, Comedy angle.
- Modal + Stage 1 cards + schema/LLM/heuristic updated; legacy aliases kept in sync.

### 2026-11-26 — Work history Open → current status stage

Completed:
- Open activates the episode and routes to its current queue-status stage (Trend Research / Script / Video / …), not always Trend Research.

### 2026-11-26 — Fix invisible View Pitch button

Completed:
- Removed `hx-disabled-elt` restore race that wiped the View Pitch label after Create Pitch.
- Re-bind View Pitch after settle; force white label/icon; keep detail CTA sticky/visible.

### 2026-11-26 — Pitch details modal above viewport (no scroll trap)

Completed:
- Modal portals to `document.body` (escapes `backdrop-filter` containing block) and locks page scroll.
- Wider compact layout, badges/grid/merch highlight, no inner scrollbar for typical pitches.

### 2026-11-26 — Frosted glass research cards

Completed:
- Trend research stage uses a pinkish frosted backdrop; Today’s top 10 / Trend Signal stay solid white for clear contrast.

### 2026-11-26 — Reduce studio left/right blank gutters

Completed:
- Raised global `--max` to 1560px; studio content body uses tighter side padding and full available width (no centered 1280px gutters).

### 2026-11-26 — Create Pitch empty pitches[] fix + step logging

Completed:
- Root cause: OpenAI returned `{"pitches":[]}` on single-topic Create Pitch; 3×60s retries then hard-failed.
- Selected-topic prompt now requires exactly 1 non-empty pitch; Luna gets `max_completion_tokens`.
- Empty/failed LLM scoring falls back to heuristic (uses Agent M take when present).
- Shorter empty-payload retries (3s); step logs tagged `[create-pitch]` / `[friction]`.

### 2026-11-26 — Remove All signals select status bar

Completed:
- Removed “Open one topic…” / “1 selected” bar above the All signals list.

### 2026-11-26 — Create Pitch auto-opens View Pitch popup

Completed:
- After Create Pitch finishes, the pitch popup opens automatically.
- CTA switches to **View Pitch** with an eye icon (re-open anytime).

### 2026-11-26 — Widen Today's top 10 viral topics card

Completed:
- Research layout grid shifted left (`1.45fr` / `0.7fr`) so the Today's top 10 viral topics list card is wider.

### 2026-11-26 — All signals open no longer jumps page scroll

Completed:
- Opening a row still swaps `#research-root` but uses `show:none` and restores window + list scroll so the page location stays put.

### 2026-11-26 — Single-select Create Pitch / View Pitch popup

Completed:
- Removed Trend Research / Approve Pitch subnav bar.
- All signals is single-select; CTA is **Create Pitch** → loading → **View Pitch** (popup card + Approve Pitch).
- Switching selection resets CTA to Create Pitch unless that topic already has a pitch.

### 2026-11-26 — Work history Open → that episode’s Trend Research

Completed:
- Open activates the clicked episode and opens Trend Research (`research=today`), not another episode’s pipeline stage.
- Mockup/scheduler ingest creates a shell, sets it active, clears research cache so Trend Research shows the new fetch.
- Create top 5 pitches reuses the active awaiting shell when present.

### 2026-11-26 — Mockup runs in background (Searching persists across pages)

Completed:
- Mockup starts a daemon ingest job and returns immediately; button stays **Searching…** while polling `/ui/queue/mockup/status`.
- Switching pages does not cancel the job; when done, Trend Research refreshes with new data + Work history shell (still no auto pitches).

### 2026-11-26 — Mockup refreshes trends + Work history row (no auto pitches)

Completed:
- Mockup scrapes/refreshes Trend Research, creates a Work history episode shell, stays on today’s research.
- No pitch cards until selected topics → Create top 5 pitches. Empty shells show “Waiting Topic Selection”.

### 2026-11-26 — Work history chrome polish

Completed:
- Trend Research main tab stays selected on Work history.
- Removed Mockup from Work history; search + Search sit in the hero above the divider.

### 2026-11-26 — Hard refresh keeps Work history / Trend research tab

Completed:
- Session + URL `research=` honored on hard refresh (no longer forced back to Trend research).
- Studio HX-Push-Url includes `research=today|history` on stage 0.

### 2026-11-26 — Trend Research no longer auto-creates pitches

Completed:
- Mockup + daily schedule = scrape/save raw signals only (`fetch_daily_raw_ingest`).
- Pitch cards only from selected topics → **Create top 5 pitches**.
- Mockup no longer creates catalog episodes or attaches pitch concepts.

### 2026-11-26 — Match Trend Research left/right card heights

Completed:
- Right detail card stays content-height (no empty gap).
- Left list card matches that height; signal list scrolls inside.

### 2026-11-26 — Trend Research header layout polish

Completed:
- Hero subtitle stays on one line (`panel-desc-single`).
- Mockup button moved up beside Today’s research / Work history toggle.
- Search box aligned on the same row as “Today’s top 10 viral topics”.

### 2026-11-26 — Remove AI summary / Agent M take from Trend Research UI

Completed:
- Research page detail no longer shows AI summary or Agent M’s take (presence + Story Match + social only).
- Page build path stops at Top-10 presence board; OpenAI enrich moved to Create Pitches → Agent M handoff.
- Validated flow: scrape A/B → presence match/squeeze → Top 10 with streams/social → AI summary on pitch handoff.

### 2026-11-26 — Live OpenAI Agent M take + Top-10 AI summaries

Completed:
- Pipeline stays scrape → cross-stream match/squeeze → Top 10 viral board → OpenAI enrichment.
- One batch OpenAI call attaches editorial `ai_summary` + Agent M cast take + fit score to each Top-10 card (`AGENT0_LIVE_TAKE` default on; heuristic fallback).
- Detail panel shows **AI summary** then **Agent M’s take** (source badge: openai / overlap+cast fit).
- Luna-safe chat payload (`max_completion_tokens`, `response_format=json_object`); `.env.example` documents `AGENT0_LIVE_TAKE`.

### 2026-11-26 — Detail panel: social as Story Match bars (no Social proof pills)

Completed:
- Removed the detail **Social proof** pills block.
- Social streams (Reddit/X/YouTube/…) now appear in the same Story Match % bars as mainstream outlets.

### 2026-11-26 — Selection only on All signals (persist on refresh)

Completed:
- Select / Create pitches only on the **All signals** tab (combined board).
- User selections persist across refresh (session + per-user store); nothing is auto-selected unless the user clicked Select.

### 2026-11-26 — Select button = original checkbox toggle behavior

Completed:
- Kept Select button UI; restored checkbox-style server toggle (`hx-swap=none` + `HX-Trigger` sync).
- Removed capture-phase optimistic JS / `hx-vals` that blocked HTMX and broke multi-select.

### 2026-11-26 — Filter-aware list tags (Mainstream / Social / All)

Completed:
- **Mainstream** tab: mainstream outlet tags only.
- **Social proof** tab: social pills only.
- **All signals**: Media × Social badge + mainstream outlets + social pills combined.

### 2026-11-26 — Trend Research list capped to Top 10 viral

Completed:
- List shows only the top 10 topics ranked for cross-stream virality (Media × Social / multi-outlet first).
- Selected topics stay visible if they fall outside that Top 10.

### 2026-11-26 — Client feedback: diversity + Media × Social cross-check

Completed:
- Soft Mainstream↔Social attach so Layer B hits join matching A topics (entity/story match).
- Rank/score boost for A+B (`has_cross_layer`); Media × Social badge + social pills on list; Social proof restored on detail.
- Soft theme anti-clone on the ranked list (max 2/theme near top; clones deferred, not deleted) so Top isn’t five political wire variants.
- Light lifestyle/suburban/youth boost when overlap is decent.

### 2026-11-26 — Fix Trend Research multi-select (up to 5)

Completed:
- Select was sticking at 1 topic when the cookie session dropped prior ids.
- Selection now persists per user in memory + session, and the client posts the intended selected list with each toggle.

### 2026-11-26 — Restored working tree to Nov 25 ~8:00 PM

Completed:
- Recovered post-commit evening Trend Research UI (Agent M take, Select button, outlet links, detail panel, fonts, Layer C removed) by replaying transcript edits up to the 8:00 PM Nov 25 checkpoint.
- Excluded all Nov 26 Media × Social / theme-diversity work.

### 2026-11-25 — Agent M take on Trend Research (always filled)

Completed:
- Agent M’s take no longer waits for a pitch-scoring run (was always “pending”).
- Each research signal now gets an immediate cast+overlap opinion (Gary/Linda/Chris/Chloe + outlets + social proof); reuses pitch-run editorial when a close match exists.
- Optional OpenAI polish via `AGENT0_LIVE_TAKE=1` (fallback-first heuristic otherwise).

### 2026-11-25 — Trend Detail Panel (Reference Layout)

Completed:
- Right-side signal detail restyled to match reference: pink confidence panel, ring + bar, debate badge, Mainstream overlap bars, Social proof pills, Agent M take card, full-width CTA.
- Content stays dynamic from presence grouping / Story Match / Layer B hits (`research_ui.py` social proof chips).
- List Select uses a button (no checkbox) with instant Selected sync; score shows `94` + `/100` + `signal score`.

### 2026-11-25 — Research Hero (Reference Layout)

Completed:
- Kept original A0–A5 studio stepper (reverted reference stepper restyle).
- Trend Research hero: `Daily signals · Updated live` kicker + segmented **Today’s research / Trend history 28 days** toggle.

### 2026-11-25 — UI Fonts → DM Sans + Space Grotesk

Completed:
- Body/UI: **DM Sans** (`--font`).
- Headings: **Space Grotesk** (`--font-heading`) on `h1–h6`, `.panel-title`, research titles/headlines.
- Mono stays IBM Plex Mono.

### 2026-11-25 — Remove Layer C from Trend Research

Completed:
- Removed **Character Niche (C)** filter tab and labels from Trend Research.
- Research presence / Story Match confidence now uses **Mainstream (A) + Social Proof (B) only** (Layer C hits excluded from grouping and averages).

### 2026-11-25 — Story Match Confidence (S/E/C/T)

Completed:
- Publisher Mainstream overlap % is now **Story Match Confidence** vs the selected/anchor trend:
  - Semantic 40% + Entity 25% + Event/context 20% + Time relevance 15%.
- Flow: fetch topic → when found on another platform, score that article with all 4 factors → bar %.
- Ring confidence = average of publisher match % across platforms (single-outlet stays early-signal).

### 2026-11-25 — Research Checkbox: No Scroll / No Auto-Select

Completed:
- Checkbox toggle no longer remounts `#research-root` (uses `hx-swap="none"` + `HX-Trigger`).
- Toggle does not change the active detail row; list scroll stays put while selection syncs in place.

### 2026-11-25 — Mainstream Overlap UI + Match Confidence

Completed:
- Mainstream overlap matches reference layout: title + pink outlet count, “Reported by…”, per-outlet pink bars with %.
- Per-platform match % from title Jaccard vs the anchor story; repeat hits on the same outlet accumulate (capped 100).
- **Confidence** = sum(platform %) ÷ platform count; drives the Unanimous ring + confidence bar and list scores.

### 2026-11-25 — Trend Research Mockup Button

Completed:
- Added **Mockup** on Trend Research (`stage_0_research.html`) to manually run the 06:00 EST Agent 0 scheduler.
- Mock from research returns to `research=today`, clears the raw-feed cache, and refreshes signals; history Mockup still lands on Trend history.

### 2026-11-25 — Presence Ranking + Layer Labels + Unanimous/Overlap

Completed:
- **Filters renamed**: Mainstream (A), Social Proof (B), Character Niche (C).
- **No scrape-time title dedupe** (`collect_all_trends`): every outlet/platform hit is kept raw.
- **Post-scrape presence merge** (`group_items_by_presence`): Jaccard-merge titles across platforms, then rank by outlet/platform/layer presence.
- **Detail panel restored**: Unanimous signal ring + copy from real presence; Mainstream overlap bars from real Layer A outlet scores; Agent M take retained.
- **Pitch create** resolves selected `topic_*` presence groups (with legacy `sig_*` fallback).

---

### 2026-11-25 — Trend Research: Real Data Only + AI Agent M Take

Completed:
- Removed fabricated detail UI (fake confidence copy, debate badges, invented social-proof counts, fake outlet % bars).
- Detail panel now shows real feed facts (source, layer, character, views, feed score), real related outlets by title overlap, and **Agent M’s take** from the latest AI ranking/pitch run (`youth_sentiment_summary` / `crash_out_angle`) when a match exists.

---

### 2026-11-25 — Agent 0 Tab Layout: Corner History + Wide Research/Approve

Completed:
- **Trend history** stays a compact corner tab in the panel header.
- **Trend Research** and **Approve pitch** are a full-width horizontal dual-tab bar beneath the header.

---

### 2026-11-25 — Agent 0 Top Tabs: Research / Approve / History

Completed:
- Removed left **Today's research / Trend history** subtabs.
- Top Agent 0 row is now three tabs: **Trend Research**, **Approve pitch**, **Trend history**.

---

### 2026-11-25 — Restore Studio Stepper Bar (A0–A5)

Completed:
- Restored top pipeline bar to prior layout: **A0 Trend Research & Approve Pitch**, **A1 Scriptwriter**, **A3 Animation & Rendering**, **A4/A5 Soon**.
- Stage 1 remains merged into A0 in the stepper; in-panel Trend Research / Approve pitch tabs are unchanged.

---

### 2026-11-25 — Agent 0: Layer C filter, ranking, fast checkbox

Completed:
- **Layer C**: Already present in All signals; Social filter was A/B conflation. Split filters to Mainstream A / Social B / **Character C**, with Layer badges on each row.
- **Ranking**: Per-layer normalized scores + quality bonus; All view round-robins A→C→B so character niche is not buried under YouTube raw scores.
- **Checkbox speed**: Toggle/open now swaps `#research-root` only (not full workspace), with a short raw-feed memory cache and capped similarity scan.

---

### 2026-11-25 — Agent 0 Trend Research UI (Today + History + Select 5)

Completed:
- **Agent 0 tabs**: Stage stepper now shows separate **Trend research** and **Approve pitch**; both stages expose matching in-panel tabs.
- **Today's research** (`stage_0_research.html`): signal list + detail panel (score, mainstream overlap, social proof, Agent M take) using current theme tokens — not the reference mock fonts/sizes.
- **Trend history · 28 days**: previous Studio queue table moved to `stage_0_history.html`.
- **Select 5 → Top 5 pitches**: session-backed multi-select on today's signals; `POST /ui/agent0/create-pitches` scores the selected topics into Gate 1 pitch cards and opens Approve pitch.
- **Helpers**: `app/trends/research_ui.py`, `load_raw_items()` in `app/trends/store.py`, research routes under `/ui/agent0/*`.

---

### 2026-11-25 — Temporal Worker Reload Hang Fix

Completed:
- **Root cause**: uvicorn `reload=True` cancelled the in-process Temporal worker on file save; lifespan never awaited/stopped that task, so Windows shutdown hung and the HTTP server died after `Worker cancelled, shutting down` INFO lines.
- **Fix (`app/infra/temporal.py`, `app/main.py`)**: track the worker task via `start_temporal_runtime` / `shutdown_temporal_runtime`, cancel with a 2s timeout on lifespan exit, treat `CancelledError` as expected reload/shutdown, and clear the Temporal client so the next boot reconnects cleanly.

---

### 2026-11-25 — Episode Title Format: EP_YYYY-Mon-DD + Same-Day (N)

Completed:
- **Studio Episode Naming (`app/studio/naming.py`)**:
  - Replaced `EP-<serial>-<YYYYMMDD>` with day-stamp titles: `EP_2026-Nov-23`.
  - Same-day extras allocate `EP_2026-Nov-23 (2)`, `(3)`, … by scanning existing episode titles (including pitch-confirmed `EP_… - Pitch` forms).
  - Month abbreviations are fixed English (`Jan`–`Dec`) so names stay locale-independent.
  - Pitch confirm still preserves the day stamp / sequence: `EP_2026-Nov-23 (2) - {pitch}`.
- **Create Path (`app/state.py`)**:
  - Blank / placeholder titles (`New Episode`, `Untitled`) now mint the day-stamp name via `make_studio_episode_name`.
- **Gateway 1 (`app/agents/agent_m_orchestrator.py`)**:
  - Stopped overwriting the episode title with the raw pitch headline; now uses `apply_confirmed_pitch_title` so the day stamp / `(N)` sequence is kept.

---

### 2026-11-24 — Studio Scriptwriter: Prompt Scroll Removal & Fullscreen Editor Mode

Completed:
- **Removed Vertical Scrollbar from Prompt Editor (`app/static/css/app.css`, `app/templates/partials/script_scene_block.html`)**:
  - Eliminated inner vertical scrolling on `.script-prompt-editor` in standard view (`overflow-y: hidden`, `resize: none`, `field-sizing: content`).
  - Added dynamic JS auto-resizing (`scrollHeight`) in [app/static/js/ui.js](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/static/js/ui.js) so the textarea automatically expands to fit 100% of the prompt content on initial load, HTMX swaps (`htmx:afterSwap`), typing, and window resizing.
- **Added Fullscreen Prompt Editor (`app/templates/partials/script_scene_block.html`, `app/static/js/ui.js`, `app/static/css/app.css`)**:
  - Added a dedicated `⛶ Fullscreen` toggle button in the prompt card header with keyboard shortcut support (`Esc` key to exit).
  - Designed `.vidu-prompt-card.is-fullscreen` fixed full-viewport overlay (`position: fixed; inset: 0; z-index: 99999; width: 100vw; height: 100vh;`) with smooth scrolling and responsive text editing for distraction-free script review.
- **Renamed Section Heading (`app/templates/partials/script_scene_block.html`)**:
  - Changed the heading of the lower screenplay details section from `Clip X:` to **`Dialogue Review`**.
- **Reordered Scriptwriter Clip Panel (`app/templates/partials/script_scene_block.html`)**:
  - Moved the **`⚡ Vidu Q4 Video Prompt & Character References`** card (`.vidu-prompt-card`) to the top of the scene panel, immediately below the scene tabs.
  - Placed the **`Dialogue Review` section** (heading, scene action & blocking, master camera, scene SFX & ambience, and screenplay dialogue cards) below the prompt card.
  - Updated helper and button tooltip texts (`"Editing prompt text updates dialogue, action, camera & SFX below"`) to reflect the new vertical orientation.

---

### 2026-11-23 — Live Production Server Fast-Forward to Master (`c0223e7`) & Verification

Completed:
- **Master Branch Verification**:
  - Validated that `users/vikas/Agent0` commit `53bc72e` was fully merged into `dev` (`40232a4`) and subsequently merged into `master` (`c0223e7`).
  - Verified `origin/master` and local `master` are identical and clean.
- **Production Deployment to AWS EC2 (`54.166.201.137`)**:
  - Connected via OpenSSH using `crashout.pem` to `ubuntu@54.166.201.137`.
  - Stashed temporary server working tree state and pulled `origin/master` (`Updating 61df528..c0223e7`, fast-forward across 26 files).
  - Executed `sudo systemctl daemon-reload` and restarted `crashout.service`.
  - Ran the test suite directly on the live server: all 6 tests in `tests/test_agent_m_retry.py` passed (`Ran 6 tests in 0.210s, OK`).
  - Verified live service status: `Active: active (running)`, Uvicorn running on port 8000, Temporal worker connected on `crash-out-production-queue`, and HTTP 200 OK verified on `/login`.

---

### 2026-11-23 — Agent M Retry Validation (3 Retries with 1-Min Gap) & Incident Test Suite

Completed:
- **Enforced 3 Automated Retries with 1-Minute Gap (`friction.py`, `agent_1_scriptwriter.py`)**:
  - Configured automated retry interval `AGENT_RETRY_INTERVAL_SECONDS` (defaults to 60s / 1 min in production).
  - Both Agent 0 (Trend Ingest) and Agent 1 (Scriptwriter) execute 3 attempts with 60-second backoff pauses before exhausting attempts.
- **Agent M Log Board & Incident Recognition (`app/agents/agent_m_orchestrator.py`)**:
  - Fixed incident detection filter in `get_system_incidents()` so `AGENT0_*` and `AGENT1_*` failure logs are surfaced on the Log Board.
  - Set severity to `"CRITICAL"` when retries reach 3.
  - Implemented one-click recovery in `orchestrator.retry_task()` for Agent 1 (`AGENT1_SCRIPT_FAILURE`), re-executing `scriptwriter_agent.generate_script()`, attaching the script to the episode, and marking the incident resolved.
- **Temporal Activity Retry Policy (`app/infra/temporal.py`)**:
  - Added `AGENT_RETRY_POLICY` with `maximum_attempts=3` and `initial_interval=timedelta(minutes=1)` to Temporal activities for Agent 0 and Agent 1.
- **Comprehensive Test Suite (`tests/test_agent_m_retry.py`)**:
  - Implemented 6 unit and integration test cases covering:
    1. Agent 0: 3 attempts, 60s gap, incident logging.
    2. Agent 1: 3 attempts, 60s gap, incident logging.
    3. Agent M Log Board: Surfacing Agent 0 and Agent 1 failures with CRITICAL severity.
    4. One-Click Retry for Agent 0: Re-running trend pipeline and resolving incident.
    5. One-Click Retry for Agent 1: Re-running scriptwriter and updating episode state.
    6. Exclusion of resolved incidents from active incident board.
  - All 6 tests passing (`Ran 6 tests in 0.225s, OK`).

---

### 2026-11-23 — Active Script Clip Tab Border Styling Update

Completed:
- **Active Scene Tab Border Color (`app/static/css/app.css`)**:
  - Replaced legacy cyan/blueish border styling (`#5eead4`) on `.scene-tab.active` with brand pink `var(--brand, #ff2d8a)`.
  - Updated both `border-color` and inset `box-shadow` to produce a clean, unified pink highlight around the currently selected script clip tab.

---

### 2026-11-23 — Medium Pacing Dialogue, Omnipresent Merch Hook & Dynamic Cast Optimization

Completed:
- **Balanced Medium Dialogue Pacing (`app/agents/agent_1_scriptwriter.py`)**:
  - Re-calibrated dialogue density from frantic rapid-fire (4–6 turns, 35–45 words) to an engaging, natural **medium spot**: 3 to 4 well-paced turns per 15s scene (approx 20–30 spoken words total, ~6–10 words per line, natural conversational speed).
  - Scene 4 (11–13s) targets 2 to 4 turns (15–25 spoken words).
  - Gives actors and animated characters breathing room for physical expressions, camera cuts, and sound triggers without awkward dead air.
- **Flexible Merch Punchline Placement in Any Scene (`agent_1_scriptwriter.py`, `agent_m_orchestrator.py`)**:
  - Removed the restriction forcing the merch punchline solely into Scene 4.
  - Instructed OpenAI to place the exact `proposed_merch_hook` in whichever scene (Scene 1, 2, 3, or 4) naturally maximizes comedic impact.
  - `_flatten_scenes()` dynamically detects which scene delivered the punchline to populate `merch_context`.
- **Dynamic Character Library Synchronization (`agent_1_scriptwriter.py`, `agent_m_orchestrator.py`)**:
  - Completely decoupled system and user prompts from hardcoded character names. All roster definitions, speaker tags, valid ID validation, and default character fallbacks pull directly from the active backend Character Library (`characters/library.json`).
  - Added characters or removed characters are immediately reflected across script generation.
- **Scene Durations & QA Thresholds (`agent_1_scriptwriter.py`, `agent_m_orchestrator.py`)**:
  - Scene 1: 15s, Scene 2: 15s, Scene 3: 15s, Scene 4: 11–13s (targeting ~12–13s, strictly totaling 56–58s).
  - Updated Orchestrator QA check threshold to $\ge 10$ dialogue lines across the episode to support the new balanced pacing.

---

### 2026-11-23 — Top Busy Loading Indicator on Refresh Buttons & Dashboard Controls

Completed:
- **Global Busy Indicator Integration (`app/templates/agent_m.html`, `app/templates/tasks_schedule.html`)**:
  - Wired `hx-indicator="#busy"` to the **"Refresh Telemetry"** button on the Agent M Supervisor page (`/agent-m`).
  - Wired `hx-indicator="#busy"` to the **"Refresh Tasks"** button on the Task & Schedule page (`/tasks-schedule`).
  - When either button is clicked, HTMX targets `#busy` (`.busy-bar`), activating the moving thin pink gradient progress bar (`var(--brand, #ff2d8a)`) across the top of the viewport.
- **Extended Feedback across Pagination & Agent Filter Tabs (`partials/agent_m_tasks_section.html`, `partials/agent_m_hitl_section.html`, `partials/agent_m_incidents_section.html`)**:
  - Added `hx-indicator="#busy"` to agent filter pills and pagination controls (Prev, Next, numbered pages) across task schedules, HITL assignments, and system error log boards.

---

### 2026-11-20 — Implemented Agent 1: Scriptwriter Agent (Dynamic OpenAI JSON Script, Dynamic Merch Embedding & Vidu Q4 Prompts)

Completed:
- **Dynamic OpenAI Script Generator (`app/agents/agent_1_scriptwriter.py`)**:
  - Completely removed static catalog mock fallbacks (`hoa_violation` and `hoa_q4_prompts`).
  - Implemented `Agent1Scriptwriter.generate_script()` powered by OpenAI `gpt-6-luna` using structured JSON mode.
  - Generates a full 4-scene (40–60s) episodic script with Gary, Linda, Chris, and Chloe.
  - Dynamically weaves the approved concept's `proposed_merch_hook` directly into Scene 4 dialogue (e.g. Chloe's livestream merch poll).
  - Synthesizes Vidu Q4 multi-character generation prompts per scene, strictly enforcing the $\le 2,000$ character budget via `app/core/prompts.py`.
- **Automated 3-Attempt QA Self-Correction & Agent M Incident Logging**:
  - Built an automated 3-attempt retry loop that validates the candidate script against `orchestrator.validate_script_qa()`.
  - In the event of a validation failure, error diagnostics are automatically injected into the subsequent attempt's user prompt for self-correction.
  - If all 3 retries fail, logs a critical incident to `system_audit_logs` in PostgreSQL and requires manual retry via Agent M.
- **Diagnostic Fix (`app/trends/pipeline.py`)**:
  - Removed remaining lingering reference to `static_fallback_concepts()` inside `fetch_live_concepts()`.
  - Replaced with live-or-cached concept loading and explicit Agent M incident requirement on full failure (zero static fallbacks).
  - Validated `fetch_live_concepts()` returning 5 live concepts with 0 diagnostics.
- **Dynamic Character Library Synchronization (`app/core/prompts.py`)**:
  - Updated `build_reference_bindings()` and `build_scene_prompt()` to resolve character profiles dynamically via `app.studio.characters.get_character(cid)`.
  - Ensures speaker names in dialogue and character bindings in Vidu Q4 prompts immediately reflect any updates or custom additions made from the `/studio?stage=0` Characters page without requiring code changes or server restarts.
- **Resolved Terminal 401 Error & Database Credential Sync (`app/auth/users.py`, `app/core/catalog.py`)**:
  - Identified root cause of terminal 401 OpenAI errors: `user_settings` in PostgreSQL contained an invalid dummy test key (`sdfghj`) saved via the web settings UI, which was overriding the valid `.env` key on user session startup.
  - Updated PostgreSQL `user_settings` with the valid encrypted OpenAI API key and model `gpt-6-luna`.
  - Added safe fallback logic in `app/auth/users.py` (`apply_user_credentials_to_config`): if a user settings key is blank or cleared, the application seamlessly falls back to the system environment variable `OPENAI_API_KEY` rather than failing.
  - Standardized `OUTPUT_DIR` import in `app/core/catalog.py` to use `app.paths.OUTPUT_DIR` as the single source of truth, removing accidental creation of `app/outputs/`.
- **End-to-End Live Verification**:
  - Ran live test with today's Pitch #1 (*Anthropic’s IPO Mints Seven Billionaires—and Turns the Genius Bar Into a Class-War Help Desk*).
  - Output verified:
    - 4 scenes, 16 dialogue lines, 52s estimated duration.
    - Setting: Apple Store Genius Bar.
    - Merch trigger: `"Prompted This"` verified in Scene 4.
    - Vidu Q4 prompts: 1269–1337 characters per scene ($\le 2000$).
    - `validate_script_qa`: **PASSED**.

---

### 2026-11-20 — Removed Static Fallbacks, Automated 3-Retry with Agent M Incident Logging & Enhanced Versatile Angles

Completed:
- **Zero Static Mock Fallback Enforcement (`pipeline.py`, `friction.py`, `concept_writer.py`)**:
  - Completely purged `static_fallback_concepts()` and `score_clusters_heuristic` mock generation fallbacks.
  - Replaced fallback degradation with an automated **3-attempt retry loop with exponential backoff** (2.0s, 4.0s).
  - Wired failures directly to Agent M (`app/db.py:log_system_incident` and `app/agents/agent_m_orchestrator.py:get_system_incidents`). If all 3 automated retries fail, it logs a critical incident requiring human review and surfaces an active "Manual Retry" action button on the Agent M Control Plane.
  - Linked Agent M `retry_task` to re-execute `fetch_daily_pitch_run(force_refresh=True)` on demand when triggered from the UI.
- **Enhanced `crash_out_angle` Versatility (`app/trends/friction.py`, `app/trends/concept_writer.py`)**:
  - Overhauled editorial system prompts to eliminate repetitive kitchen/driveway settings.
  - Mandated dynamic rotation across diverse suburban arenas:
    - *Retail/Consumer*: Apple Store Genius Bar, big-box self-checkout kiosks, Costco aisles, drive-thrus, car dealerships.
    - *Suburban Civic & Sports*: High school football bleachers, pickleball courts, HOA emergency meetings, school board podiums.
    - *Infrastructure & In-Transit*: County fair midway, stalled Cybertruck charging queues, airport TSA lines.
  - Expanded character mechanics: Gary's sovereign-citizen legal logic & overbuilt prepper carts, Linda's seed-paper petitions & "conscious consumption", Chris's arbitrage bots & prediction markets, Chloe's livestream polls ("Retrieve Dad or let him learn?") and bootleg merch drops.
- **Live Verification**:
  - Executed live Agent 0 run with zero mock fallbacks.
  - Generated 5 high-energy, versatile pitches:
    1. *Anthropic IPO Mints Billionaires* (Setting: Apple Store Genius Bar)
    2. *Cyber Outages Oust Security Chief* (Setting: Big-box store self-checkout kiosks)
    3. *GTA VI Copycat Warnings* (Setting: High school football bleachers & marching band)
    4. *Army Delays Demolition* (Setting: County fair midway & emergency cart)
    5. *Permitting Bill Sparks Turf War* (Setting: Neighborhood pickleball court & HOA golf cart)

---

### 2026-11-20 — Structured Outputs & Storage Hierarchy (Episode-Scoped & Agent 0 Subdirectories + S3 Media Pipeline)

Completed:
- **Agent 0 Clean Subfolder Hierarchy (`app/trends/store.py`)**:
  - Organized `outputs/agent0/` into dedicated functional subfolders:
    - `outputs/agent0/raw/`: Stores all daily scraped news/social snapshots (`raw_YYYY-MM-DD.json` and timestamped snapshots).
    - `outputs/agent0/pitches/`: Stores all generated daily pitch batches (`pitch_run_YYYY-MM-DD.json` and timestamped snapshots for run archives).
    - `outputs/agent0/topics/`: Stores persistent deduplication indexes (`episode_topics.json`).
    - `outputs/agent0/latest_pitch_run.json`: Fast root pointer for immediate dashboard UI rendering.
  - Implemented automatic 7-day auto-pruning (`prune_agent0_history`) ensuring stale raw and pitch archives older than 7 days are automatically purged to prevent disk accumulation.
- **Episode-Scoped Folder Architecture (`app/paths.py`, `app/state.py`)**:
  - Scoped all episode outputs into `outputs/episodes/<ep_id_Title>/`.
  - Added dedicated media subfolders inside each episode: `video/` (`scene_*.mp4`, `merged_60s.mp4`) and `audio/` (voiceover stems).
  - Maintained complete backward compatibility in `episode_dir()`, `scene_file_candidates()`, and `merged_file_candidates()` for legacy flat folders.
  - Migrated 8 existing episode folders and organized their media into `outputs/episodes/<folder>/video/` and `audio/`.
- **AWS S3 Cloud Storage & Media Streaming (`app/infra/storage.py`)**:
  - Enhanced S3 sync for `.mp4`, `.webm`, `.wav`, `.mp3`, `.json`, and `.png` assets.
  - Added `get_media_url()`: on production live server with `AWS_S3_BUCKET` configured, video and audio stream directly from S3 pre-signed or CDN URLs, keeping live server CPU, RAM, and bandwidth usage at 0% during playback.
  - Seamless offline fallback: serves locally from `/outputs/episodes/...` when S3 credentials are not set.

---

### 2026-11-20 — Optimized Agent 0 for 06:00 EST Daily Schedule & Strict 24-Hour Recency

Completed:
- **Strict 24-Hour Window Enforcement (`sources_a.py`, `sources_b.py`, `sources_c.py`)**:
  - Added strict timestamp validation: any article or social post with `age_hours > 24.0` is discarded immediately.
  - Appended `when:24h` parameter to Google News search queries across mainstream news, subreddits, and character niche queries.
  - Aligned data collection with the 06:00 EST daily cron schedule (`scheduler.py`) so pitches only reflect the preceding 24 hours of breaking news.
- **Data Volume Optimization (Lean ~130 Items)**:
  - Trimmed per-feed limits from 10–15 items down to top 4–5 breaking items across core high-signal outlets.
  - Reduced raw collection from 551 items down to 136 items (Layer A: 56, Layer B: 39, Layer C: 41).
  - Validated age distribution: minimum 0.0h, maximum 24.0h, average 10.2h old, **0 items older than 24h**.
  - Reduced clustering computation by >90% while maintaining rich multi-layer collision coverage.

---

### 2026-11-20 — Enhanced Agent 0 (Layer C, Semantic Clustering Calibration & End-to-End Live Validation)

Completed:
- **Resilient Character Feeds (`app/trends/sources_c.py`)**:
  - Upgraded Gary's tech & layoff feeds to direct RSS syndication (`TechCrunch`, `The Verge`, `r/Layoffs`, `r/cscareerquestions`, `r/overemployed`), collecting 50 character-specific items.
  - Upgraded Linda's suburban wellness feeds (`MindBodyGreen`, `Self Wellness`, `wellness+trend+OR+stanley+cup+OR+botox`, `r/parenting`, `r/SkincareAddiction`, `r/ShitMomGroupsSay`), collecting 50 items.
  - Upgraded Kids' feeds (`Dexerto`, `Tubefilter`, `streamer+drama+OR+influencer+controversy`, `r/CreatorServices`, `r/LivestreamFail`), collecting 50 items.
- **Semantic Clustering Calibration (`app/trends/cluster.py`)**:
  - Calibrated `SIMILARITY_THRESHOLD` from 0.82 to 0.58 to capture genuine multi-source news events (e.g. Anthropic IPO, tech outages, smart home failures).
  - Defined `cross_layer` to detect any multi-layer collision across Mainstream (A), Youth Reddit (B), and Character feeds (C).
  - Implemented batched embeddings (100 items per chunk) preventing payload limits on high raw item volumes.
  - Sorted clusters by cross-layer collision status, layer diversity, member count, and score.
- **OpenAI Model Compatibility Fix (`app/trends/friction.py`, `app/trends/concept_writer.py`)**:
  - Identified that `OPENAI_MODEL=gpt-6-luna` strictly requires default temperature (1.0); passing `temperature=0.55` returned HTTP 400.
  - Made temperature parameter conditional so reasoning/luna models execute cleanly without parameter rejections.
- **End-to-End Live Pipeline & Storage Verification**:
  - Verified full `collect_all_trends()` collecting 560 unique items across A (211), B (200), and C (140).
  - Verified `outputs/agent0/raw_2026-11-20.json` (206 KB) storing raw ingested records.
  - Verified live OpenAI scoring generating 5 top friction pitches (e.g., *AI Outages Turn Smart Home Dumb*, *Screen-Time App Turns Detox Competitive*, *Meta's $300 Muse Charm*).
  - Verified `outputs/agent0/latest_pitch_run.json` and Gate 1 concept card mapping (`trend_ingest_agent.fetch_trending_concepts()`).

---

### 2026-11-20 — Enhanced Agent 0 (Layer B: Youth Social & Meme Trends with Reddit Syndication)

Completed:
- **Resilient Reddit Syndication Engine (`app/trends/sources_b.py`)**:
  - Identified that direct unauthenticated requests to `reddit.com/r/{sub}.json` fail with HTTP 403 Forbidden due to Reddit's anti-scraping policy.
  - Implemented `_fetch_reddit_syndication` which fetches authenticated Google News direct RSS syndication for target subreddits (`r/GenZ`, `r/mildlyinfuriating`, `r/HOA`, `r/antiwork`, `r/Suburbanhell`, `r/popculturechat`, `r/OutOfTheLoop`, `r/WorkReform`, `r/ExplainTheJoke`, `r/TikTokCringe`).
  - Automatically strips Reddit attribution suffixes (` - Reddit`) and sanitizes post descriptions.
  - Retained optional authenticated PRAW path when `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` are provided.
- **Added Dedicated Youth & Viral Feeds (`app/trends/sources_b.py`)**:
  - Added dedicated feeds for `TikTok Trends`, `Gen Z Culture & Slang`, and `Suburban & Neighbor Feuds`.
  - Added HTML entity unescaping, tag stripping, and recency parsing (`_clean_html_text`, `_parse_age_hours`).
- **Verification**:
  - Executed live `collect_layer_b()` test: collected 200 items across all 10 subreddits, TikTok trends, Gen Z slang, and Know Your Meme.

---

### 2026-11-20 — Enhanced Agent 0 (Layer A: Mainstream News Ingestion & Recency Scoring)

Completed:
- **Repaired Broken Mainstream RSS Endpoints (`app/trends/sources_a.py`)**:
  - Fixed Associated Press and Reuters Google News queries from deprecated `allinurl:...` to `site:apnews.com` and `site:reuters.com`, restoring full 100-article stream capacity.
  - Replaced 403-blocked Morning Brew feed with high-signal direct feeds: CBS News, ABC News, Google News Nation, and Google News Business.
  - Added CNBC US top stories to the briefing layer alongside Axios AM, CNBC Make It, and TechCrunch.
- **HTML Sanitization & Snippet Cleanup (`app/trends/sources_a.py`)**:
  - Implemented `_clean_html_text` unescaping HTML entities and cleanly stripping all raw HTML tags (`<a href>`, font tags, lists) from article snippets before passing downstream.
- **Recency Parsing & Velocity Scoring (`app/trends/sources_a.py`)**:
  - Implemented `_parse_age_hours` parsing RFC-822/ISO `pubDate` timestamps with timezone awareness.
  - Added dynamic recency scoring boost (+10 points for articles $\le 6\text{h}$ old, +5 points for articles $\le 24\text{h}$ old).
- **Commercial Ad/Spam Filtering on Google Trends RSS (`app/trends/sources_a.py`)**:
  - Blocked commercial legal/insurance keywords (lawyer, attorney, insurance quote, personal loan, etc.) so only genuine cultural/suburban news and consumer events enter the pipeline.
- **Verification**:
  - Executed live `collect_layer_a()` test: collected 216 unique articles with 100% feed health across AP, Reuters, CNN, Fox News, NY Post, CBS, ABC, Google News, Axios, CNBC, and TechCrunch.

---

### 2026-11-20 — Enhanced Login Card: Increased Size, Enhanced Logo & Moved Inside Card

Completed:
- **Moved Logo & Brand Identity Inside Card (`app/templates/auth_login.html`, `app/templates/auth_base.html`)**:
  - Relocated `.auth-brand` and tagline from floating on the backdrop into `.auth-card-brand` inside `.auth-card`.
  - Added a subtle separator line between the brand identity and the form header.
- **Increased Logo & Brand Size (`app/static/css/app.css`)**:
  - Increased circular badge `.brand-mark` size from 42px to 68px (>60% larger), with glowing hot pink border (`3px solid var(--brand)`) and elevated drop shadow.
  - Increased typography size for `.brand-title` to `clamp(1.35rem, 3.2vw, 1.65rem)` with dark, high-contrast text (`var(--text)`) suitable for the light card background.
- **Expanded Login Card Dimensions & Layout (`app/static/css/app.css`)**:
  - Increased `.auth-center` max-width from 380px–420px to 500px–520px on desktop screens.
  - Increased card padding to `clamp(2rem, 5vw, 2.75rem)` with modern 20px rounded corners.
  - Enhanced input fields and sign-in button with comfortable padding and height.

---

### 2026-11-20 — Synchronized Local Branches (`dev`, `users/vikas/login-setup`) with `master`

Completed:
- **Branch Fast-Forward & Code Alignment**:
  - Fast-forward merged `master` (commit `4e5831f`) into `dev` and `users/vikas/login-setup`.
  - Confirmed all branches point to the identical commit hash and codebase state as `master`.

---

### 2026-11-19 — Assigned All Server Episodes & Pipeline Data to Active User (`crashoutv.series@gmail.com`)

Completed:
- **Active User ID Verification on Production Server (`54.166.201.137`)**:
  - Confirmed active production user ID for `crashoutv.series@gmail.com` is `2`.
- **Episodes Data Association**:
  - Updated all 9 episode records on disk (`episode.json` files in `outputs/`) with `user_id = 2`.
  - Updated `pipeline_index.json` and in-memory `state_manager` mapping all episodes to user `2`.
  - Added `user_id` column to PostgreSQL `episodes` table and populated all 9 episodes with `user_id = 2`.
- **Other Pipeline & System Data Association**:
  - Updated custom catalog entries in `outputs/custom_catalog.json` with `user_id = 2`.
  - Assigned all pending/system notification rows in PostgreSQL `notifications` table to `user_id = 2`.
- **Service Restart & Live Verification**:
  - Restarted `crashout.service` systemd daemon on the production server.
  - Verified authenticated live requests with `crashoutv.series@gmail.com` session:
    - `/episodes` library correctly renders all 4 finished episodes (Episodes 1, 2, 3, 4).
    - `/queue`, `/tasks`, `/notifications`, and `/orchestrator` show all assigned studio episodes, tasks, and alerts.

---

### 2026-11-19 — Updated Live Production Credentials & Removed Test User

Completed:
- **Production Admin Account Activated**:
  - Configured live production database (`admin.crashout.tv` / PostgreSQL) and local database with admin user:
    - **Email**: `crashoutv.series@gmail.com`
    - **Password**: `CrashOut2026!Admin` (bcrypt hashed with 12 rounds)
    - **Display Name**: `Crash Out Admin`
  - Ensured associated `user_settings` record exists.
- **Test User Removal**:
  - Purged `test@gmail.com` (and any related test records) from both live production and local databases.
- **Live Authentication Verification**:
  - Executed HTTPS authentication check against `https://admin.crashout.tv/login`:
    - `crashoutv.series@gmail.com` / `CrashOut2026!Admin`: returns HTTP 303 Redirect to `/` and issues valid 7-day `crashout_jwt` cookie.
    - `test@gmail.com` / `test123`: rejected with HTTP 400 Bad Request ("Invalid email or password").
- **UI Template Cleanup (`app/templates/base.html`)**:
  - Updated user display name fallback from `'Test'` to `'Admin'`.

---

### 2026-11-19 — Deployed Latest Master Codebase to Production (`admin.crashout.tv`)

Completed:
- **Codebase Fast-Forward to Master on EC2 (`54.166.201.137`)**:
  - Connected securely via SSH using `crashout.pem`.
  - Fast-forward pulled latest `origin/master` (Commit `9367bd5`) into `/var/www/Crash_Out`.
  - Verified all dependencies in `/var/www/Crash_Out/venv` are satisfied.
- **Database Migrations on Production**:
  - Executed migration `006_add_openai_settings.sql` (added `openai_api_key_enc`, `openai_model` columns) in PostgreSQL.
  - Confirmed PostgreSQL schema is fully up to date.
- **Service Restart & Health Verification**:
  - Restarted `crashout.service` systemd daemon.
  - Verified Uvicorn process is running on `0.0.0.0:8000` with Temporal schedule `agent0-daily-6am-est` active.
  - Performed live HTTP/HTTPS smoke checks against `http://127.0.0.1:8000/login` and `https://admin.crashout.tv/login` returning HTTP 200 OK.

---

### 2026-11-19 — Added OpenAI API Key Configuration in Settings (Simplified UI)

Completed:
- **Database Schema Migration (`migrations/006_add_openai_settings.sql`)**:
  - Added encrypted API key and model selection columns (`openai_api_key_enc`, `openai_model`) to PostgreSQL table `user_settings`.
  - Executed migration safely via `app/db.py` (`run_migrations()`).
- **Encrypted Storage & Process Config Binding (`app/auth/users.py`)**:
  - Extended `UserSettings` dataclass with `openai_api_key_enc`, `openai_model`, `has_openai_key`, and `decrypted_openai_key()`.
  - Implemented `update_openai_settings(user_id, api_key=..., clear_api_key=..., model=...)`.
  - Added `apply_user_credentials_to_config(user_id)` to sync decrypted user OpenAI keys into `config.openai_api_key`, `config.openai_model`, `os.environ["OPENAI_API_KEY"]`, and `os.environ["OPENAI_MODEL"]`.
  - Updated `settings_public_view()` to securely mask the OpenAI API key before returning to client templates.
- **Settings Endpoint & Context (`app/auth/routes.py`)**:
  - Added `POST /settings/openai` endpoint to save or clear OpenAI API credentials (`openai_api_key`, `clear_openai_key`).
- **UI Configuration Panel (`app/templates/settings.html`)**:
  - Added clean "OpenAI API Credentials" panel placed alongside Vidu API in the Settings grid.
  - Simplified header and status bar by removing explanatory agent copy, `.env` override hints, and model selection.
  - Focuses cleanly on the status chip (`Key on file` masked or `No key saved`), "Clear stored key" button, and password input to save a new API key.
- **Verification**:
  - Verified `GET /settings` renders without the model selection dropdown (HTTP 200).
  - Verified `POST /settings/openai` encrypts key cleanly via `TestClient`.
  - Verified key clearing resets credentials.

---

### 2026-11-19 — Implemented Social Engagement & Reverted Merchandising Store Cards to Previous UI

Completed:
- **Per-Channel Social Engagement Tracking Widgets (`app/templates/dashboard.html`, `app/studio/analytics.py`)**:
  - Replaced the static placeholder cards on the main dashboard (`/`) with interactive live tracking widgets for:
    - **YouTube Shorts:** Total Views (482.4K), Subscribers (42.8K), Avg Duration (48s), Shares (4,210), Engagement (9.4%).
    - **TikTok:** Total Views (1.28M), Followers (118.5K), Avg Watch Time (54s), Comments (2,840), Engagement (11.2%).
    - **Instagram Reels:** Total Views (645.8K), Followers (68.2K), Avg Watch Time (46s), Saves (3,120), Engagement (8.7%).
  - Added interactive **Timeframe Switcher** (`Last 24 Hours`, `Last 7 Days`, `Last 30 Days`) with client-side fast tab switching for views and subscriber growth deltas (+ / - counts and %).
  - Direct channel navigation buttons (`Channel ↗`) per card.
- **Reverted Merchandising & Store Section to Previous UI (`app/templates/dashboard.html`)**:
  - Reverted the Shopify performance cards back to the original *Merchandising & Store Integration* cards:
    - *Store Connection* (Print-on-Demand · Setup Required · Shopify & Stripe webhooks in development).
    - *Merch Items* (Episode Punchline Apparel · Catalog · Automated hoodie punchlines from Agent 4).
    - *Total Merch Sales* ($0.00 USD · Live).

---

### 2026-11-19 — Real-Time Mobile Push Notifications (HITL, Errors & Publishing Alerts) + Topbar Bell & Telegram Bot Integration

Completed:
- **Telegram Bot Configuration & Auto-Detection**:
  - Linked official studio bot `@CrashhOut_bot` (`https://t.me/CrashhOut_bot`).
  - Saved bot token encrypted in PostgreSQL user settings and added fallback in `.env` (`TELEGRAM_BOT_TOKEN`).
  - Implemented `detect_telegram_chat_id` and endpoint `POST /settings/notifications/detect-chat-id` to automatically discover and pair the user's Chat ID upon sending `/start` to `@CrashhOut_bot`.
- **Real-Time Mobile Push Dispatcher (`app/infra/notifications.py`)**:
  - Implemented asynchronous, non-blocking notification engine supporting instant Telegram Bot push notifications (`POST https://api.telegram.org/bot<token>/sendMessage`) and persistent in-app notifications in PostgreSQL.
  - Formatted rich HTML alerts with mobile deep-link action buttons directly routing to screens on `admin.crashout.tv` (configurable via `ADMIN_BASE_URL` / `CRASHOUT_BASE_URL`).
  - Implemented offline graceful fallbacks: catches network timeouts, missing credentials, or API errors without ever blocking the HTTP request pipeline.
- **Automated Pipeline Triggers**:
  - **HITL Approval Gates (`notify_hitl_gate`)**: Automatically fired when a Pitch Card batch (Gate 1), Script & Merch Trigger (Gate 2), 9:16 Master Video Review (Gate 3), Merch & Distribution Package (Gate 4), or Guerrilla Seeding (Gate 5) awaits human sign-off, deep-linking directly to `/studio?stage=X&episode=EP_ID`.
  - **Critical Errors & SLA Alerts (`notify_critical_error`)**: Fired on agent failures, API outages (Vidu, ElevenLabs, OpenAI), and retry limit breaches recorded in `app/db.py` (`log_system_incident`), deep-linking to `/agent-m#system-log-board`.
  - **Episode Published (`notify_episode_published`)**: Fired upon episode publication confirmation with live links for YouTube Shorts, TikTok, and Instagram Reels.
- **Top Navigation Bar Bell Icon (`app/templates/base.html`)**:
  - Placed a dedicated notification bell icon directly before the Crash Out Admin profile details in the top navigation bar.
  - Linked to `/notifications` with an unread badge indicator showing total unread alert count across all pages.
- **Dedicated Notifications Page (`/notifications` & `app/templates/notifications.html`)**:
  - Added filter tabs: `All Notifications`, `✋ HITL Approvals`, `🚨 Critical Errors & SLA`, `🚀 Published Episodes`, and `Unread Only`.
  - Includes deep-link action buttons (`[Review Gate in Studio ↗]`, `[Inspect on System Board ↗]`, `[View Episode Live ↗]`), Telegram delivery badges (`📱 Telegram Delivered` vs `🔔 In-App Bell`), relative timestamps, and one-click "Mark as Read" / "Mark All as Read" actions.
  - Built-in pagination supporting growing notification history.
- **Settings Page Telegram Bot & Preferences (`app/templates/settings.html`, `app/auth/routes.py`, `app/auth/users.py`)**:
  - Added "Real-Time Mobile Push & Telegram Notifications" panel with toggle to enable/disable mobile push.
  - Encrypted Telegram Bot Token storage (Fernet / AES-256) and Telegram Chat ID input with instructions for `@userinfobot`.
  - Granular event toggles: HITL Approval Gates, Critical Errors & SLA Incidents, and Episode Published Confirmations.
  - Added "Send Test Telegram Notification 📱" action for instant mobile verification.
- **Database Schema Migration (`migrations/005_create_notifications_and_user_notification_settings.sql`, `docker/init-scripts/01-init.sql`)**:
  - Created `notifications` table in PostgreSQL with indexes on `user_id`, `category`, and `is_read`.
  - Added notification preference columns and encrypted token field to `user_settings`.

---

### 2026-11-19 — Resolved Temporal Web UI 500 Error & Configured HTTPS Access on Port 8088

Completed:
- **Purged Obsolete UTC Schedule (`agent0-daily-6am-utc`)**:
  - Deleted legacy schedule `agent0-daily-6am-utc` from both local and remote EC2 Temporal clusters.
  - Confirmed the single active schedule remaining on both clusters is `agent0-daily-6am-est` (Daily 06:00 EST / America/New_York).
- **Root Cause & Fix for Temporal UI 500 Error**:
  - Re-attached `crashout-temporal-ui` container to `crashout-network` with `TEMPORAL_ADDRESS=crashout-temporal:7233` and proper CORS headers.
  - Eliminated the `connection refused` dialing error on `172.17.0.1:7233`.
- **Configured Production HTTPS for Temporal UI**:
  - Bound `crashout-temporal-ui` to internal localhost port `127.0.0.1:8080`.
  - Added SSL reverse-proxy server block in `/etc/nginx/conf.d/crashout.conf` listening on `8088 ssl` using the trusted Let's Encrypt certificate for `admin.crashout.tv`.
  - Successfully reloaded Nginx and verified live public HTTPS access on `https://admin.crashout.tv:8088/`.

---

### 2026-11-19 — Implemented Agent M Master Orchestrator Status Panel, System Error Board & HITL Queue

Completed:
- **Dedicated Agent M Status Panel (`/agent-m` & `/orchestrator`)**:
  - Implemented a dedicated Master Supervisor Panel completely separated from the step-by-step creative studio pipeline (`/studio`).
  - Added primary sidebar navigation entry in `app/templates/base.html` styled with high-contrast icon and dynamic HITL pending badge counter.
  - Sourced full telemetry via `AgentMOrchestrator` in `app/agents/agent_m_orchestrator.py` and endpoints in `app/ui.py`.
- **HITL Assignments (What is Waiting for My Approval)**:
  - Aggregates all episodes currently paused at Gateways 1 through 5:
    - Gateway 1: Trend Pitch Selection (Agent 0)
    - Gateway 2: 4-Scene Script & Merch Trigger Review (Agent 1)
    - Gateway 3: 9:16 Master Video & Audio QA Review (Agents 2 & 3)
    - Gateway 4: Merch & Distribution Package Review (Agent 4)
    - Gateway 5: Guerrilla Seeding & Publishing Sign-off (Agent 5)
  - Implemented real-time **SLA Timers**: Tracks elapsed time since entering the gateway and classifies status into `ON TRACK` (< 2h, green), `NEEDS ATTENTION` (2h–6h, amber), or `SLA BREACHED` (> 6h, red).
  - Provided deep-link buttons directly navigating into the exact Studio stage (`/studio?stage=X&episode=EP_ID`) plus one-click "Quick Sign-Off" action right from the supervisor board.
- **Real-Time System Error & Incident Log Board**:
  - Built centralized monitoring board tracking failed generation jobs, Vidu Q4 API timeouts, FFmpeg merge errors, and retry attempts.
  - Implemented one-click **"Retry Task"** action (`POST /agent-m/incidents/{incident_id}/retry`) that clears the failed job lock, increments the retry counter, logs an audit trail event in PostgreSQL `system_audit_logs`, and immediately re-triggers generation via HTMX.
  - Added "Simulate Test Incident" button (`POST /agent-m/test-incident`) allowing instant demonstration and verification of incident detection and resolution.
- **Temporal Workflow Engine & Production Queue Telemetry**:
  - Live query of Temporal server at `localhost:7233`, namespace `default`, and task queue `crash-out-production-queue`.
  - Displays registered native Schedule `agent0-daily-6am-est` (Daily 06:00 EST cron) and active workflow executions.
- **Per-Agent Supervision & Transparency Roster**:
  - Outlines live operational roles, execution cadence, and health status for Agent M (Master Supervisor), Agent 0 (Trend Ingest), Agent 1 (Scriptwriter), Agents 2 & 3 (Vidu Video & Audio), Agent 4 (Publisher/Shopify), and Agent 5 (Guerrilla Seeder).
- **PostgreSQL Audit Logging & Template Fixes**:
  - Added `log_system_incident()` and `list_system_audit_logs()` in `app/db.py` to persist all incident and recovery actions in PostgreSQL.
  - Corrected `TEMPLATES_DIR` and `STATIC_CSS_PATH` resolution in `app/auth/routes.py` to properly reference `app/templates` from the domain subpackage.
- **Pagination for HITL Assignments & Log Board**:
  - Implemented standalone pagination helper `paginate_items()` in `app/agents/agent_m_orchestrator.py` with page bounds, item count range trackers (`Showing X–Y of Z items`), and page pill lists.
  - Sliced HITL assignments into compact pages (default 3 cards per page) with dedicated endpoint `GET /ui/agent-m/hitl?page=X`.
  - Sliced Log Board incident logs into compact pages (default 5 rows per table) with dedicated endpoint `GET /ui/agent-m/incidents?page=X`.
  - Modularized HTML partials: created `app/templates/partials/agent_m_hitl_section.html` and `app/templates/partials/agent_m_incidents_section.html`.
  - Added HTMX-powered pagination bars: `« Prev`, numbered page buttons, and `Next »` that swap only the relevant container without triggering full page reloads or layout jump.
- **100% Real Live Data Alignment (Zero Placeholder/Dummy Metrics)**:
  - Audited all metrics across Agent M, Temporal engine, and the 6 agents:
    - **Temporal Telemetry**: Dynamically queries `agent0-daily-6am-est` schedule description from Temporal cluster to extract actual `next_action_times` (formatted in UTC) and `num_actions` total execution counts, replacing hardcoded cadence strings.
    - **Agent M**: Computes live managed episodes count, completed episodes count (`gateway >= 6` / `COMPLETED`), and active HITL pending approvals count directly from `state_manager.episodes`.
    - **Agent 0**: Dynamically queries `load_latest_pitch_run()` for exact run date, ingested pitch count, and Gate 1 pending count.
    - **Agent 1**: Dynamically aggregates authored scripts, merch triggers, and Gate 2 pending review queue.
    - **Agents 2 & 3**: Dynamically sums rendered scene MP4 clips (28 clips), merged master 9:16 videos (7 videos), active in-flight jobs, and Gate 3 QA queue.
    - **Agent 4**: Derives packaged social/Shopify items and Gate 4 sign-offs.
    - **Agent 5**: Derives guerrilla seeding campaigns and Gate 5 sign-offs.
  - Added dynamic metrics badges (`📊`) to each agent card in `app/templates/partials/agent_m_telemetry.html`.
- **Per-Agent Task Transparency & Schedule (Agent M + Agents 0–5)**:
  - Implemented dedicated task log & schedule view for each individual agent (Agent M, Agent 0, Agent 1, Agents 2 & 3, Agent 4, Agent 5) plus an "All Agents" unified view.
  - **Completed (Last 24 Hours)**:
    - Queries real executed work from PostgreSQL `system_audit_logs`, `agent0_pitch_runs`, `generation_jobs`, and episodic state machines.
    - Accurately reports final status: `Success` (green), `Failed` (red), or `Retrying` (amber with attempt count).
    - Details task title, owning agent, target episode/scope, execution time with relative time ago, and output evidence.
    - Integrated clean pagination (default 6 tasks/page) with `« Prev`, numbered page pills, and `Next »` controls via HTMX.
  - **Active & Upcoming (Today)**:
    - Real-time tracking of in-flight render jobs, active deduplication buffers, and episodes waiting on human sign-off per agent.
  - **Scheduled (Tomorrow)**:
    - Lists queued cron tasks (e.g. Agent 0 daily 06:00 EST cron), automated script/render triggers, and continuous supervisor health audits.
  - **Interactive Agent Selector Tabs**:
    - Added pill tabs with task counters (`All Agents (43)`, `🛡️ Agent M (13)`, `🌐 Agent 0 (1)`, `✍️ Agent 1 (8)`, `🎬 Agents 2 & 3 (19)`, `🏷️ Agent 4 (1)`, `🚀 Agent 5 (1)`).
    - Sourced partial swap endpoint `GET /ui/agent-m/agent-tasks?agent_id=X&page=Y` and wired direct `"View 24h Log"` buttons from each agent roster card.
- **Moved Task & Schedule to Dedicated Sidebar View & Fixed Tab Switching**:
  - Created a dedicated page `/tasks` (and `/tasks-schedule`) with its own template `app/templates/tasks_schedule.html`.
  - Added new primary sidebar navigation entry `Task & Schedule` in `app/templates/base.html` located directly beneath `Agent M — Orchestrator`.
  - Completely moved `Per-Agent Task Transparency & Schedule (Agent M + Agents 0–5)` card view to `/tasks` and removed it from `app/templates/partials/agent_m_telemetry.html` and `app/templates/agent_m.html`.
  - Fixed tab switching reset bug:
    - Root cause: Agent M's `#agent-m-telemetry-container` was polling `/ui/agent-m/telemetry` every 15s and replacing innerHTML with default `agent_id="all"`, wiping out user tab selections.
    - Solution: Removing the task section from the polling container, and adding `hx-push-url="/tasks?agent_id=..."` to all agent tab buttons and pagination controls so the selected tab and page persist in the URL and stay locked indefinitely.
  - Added direct link buttons on each agent card in Agent M's roster: `View 24h Log »` navigating to `/tasks?agent_id={{ agent.id }}`.
- **System Verification**:
  - Verified 100% clean compilation and test execution on the running server (`GET /agent-m` -> 200 OK, `GET /ui/agent-m/telemetry` -> 200 OK, `GET /ui/agent-m/hitl` -> 200 OK, `GET /ui/agent-m/incidents` -> 200 OK, test incident creation and 1-click retry -> 200 OK).

---

### 2026-11-19 — Completed Full Codebase Migration to Domain Packages (Removed Root Files)

Completed:
- **Cleaned Up `app/` Root Directory**:
  - Replaced all root-level duplicate and shim files (`auth_users.py`, `auth_middleware.py`, `auth_routes.py`, `security.py`, `personas.py`, `prompts.py`, `catalog.py`, `storage.py`, `temporal_setup.py`, and `logging_framework.py`).
  - The root `app/` folder is now down to only 7 essential top-level entry files:
    - `main.py` (FastAPI app factory & ASGI routes)
    - `ui.py` (Frontend HTMX/Jinja view router)
    - `config.py` (Platform credentials & runtime settings)
    - `paths.py` (Filesystem single source of truth)
    - `db.py` (PostgreSQL connection pool & query helpers)
    - `state.py` (Episode model & state machine)
    - `migrations.py` (Postgres schema migrations)
- **Updated All Internal Imports Across Codebase**:
  - Replaced all imports in `app/main.py`, `app/ui.py`, `app/config.py`, `app/agents/*`, `app/engines/*`, `app/studio/*`, and `app/trends/*` to point directly to `app.auth.*`, `app.core.*`, and `app.infra.*`.
- **Per-Agent Task Transparency & Schedule (Agent M + Agents 0–5)**:
  - Implemented dedicated task log & schedule view for each individual agent (Agent M, Agent 0, Agent 1, Agents 2 & 3, Agent 4, Agent 5) plus an "All Agents" unified view.
  - **Completed (Last 24 Hours)**:
    - Queries real executed work from PostgreSQL `system_audit_logs`, `agent0_pitch_runs`, `generation_jobs`, and episodic state machines.
    - Accurately reports final status: `Success` (green), `Failed` (red), or `Retrying` (amber with attempt count).
    - Details task title, owning agent, target episode/scope, execution time with relative time ago, and output evidence.
    - Integrated clean pagination (default 6 tasks/page) with `« Prev`, numbered page pills, and `Next »` controls via HTMX.
  - **Active & Upcoming (Today)**:
    - Real-time tracking of in-flight render jobs, active deduplication buffers, and episodes waiting on human sign-off per agent.
  - **Scheduled (Tomorrow)**:
    - Lists queued cron tasks (e.g. Agent 0 daily 06:00 EST cron), automated script/render triggers, and continuous supervisor health audits.
  - **Interactive Agent Selector Tabs**:
    - Added pill tabs with task counters (`All Agents (43)`, `🛡️ Agent M (13)`, `🌐 Agent 0 (1)`, `✍️ Agent 1 (8)`, `🎬 Agents 2 & 3 (19)`, `🏷️ Agent 4 (1)`, `🚀 Agent 5 (1)`).
    - Sourced partial swap endpoint `GET /ui/agent-m/agent-tasks?agent_id=X&page=Y` and wired direct `"View 24h Log"` buttons from each agent roster card.
- **Moved Task & Schedule to Dedicated Sidebar View & Fixed Tab Switching**:
  - Created a dedicated page `/tasks` (and `/tasks-schedule`) with its own template `app/templates/tasks_schedule.html`.
  - Added new primary sidebar navigation entry `Task & Schedule` in `app/templates/base.html` located directly beneath `Agent M — Orchestrator`.
  - Completely moved `Per-Agent Task Transparency & Schedule (Agent M + Agents 0–5)` card view to `/tasks` and removed it from `app/templates/partials/agent_m_telemetry.html` and `app/templates/agent_m.html`.
  - Fixed tab switching reset bug:
    - Root cause: Agent M's `#agent-m-telemetry-container` was polling `/ui/agent-m/telemetry` every 15s and replacing innerHTML with default `agent_id="all"`, wiping out user tab selections.
    - Solution: Removing the task section from the polling container, and adding `hx-push-url="/tasks?agent_id=..."` to all agent tab buttons and pagination controls so the selected tab and page persist in the URL and stay locked indefinitely.
  - Added direct link buttons on each agent card in Agent M's roster: `View 24h Log »` navigating to `/tasks?agent_id={{ agent.id }}`.
- **System Verification**:
  - Verified 100% module import success (`60/60 modules loaded with 0 errors`).
  - Ran automated live HTTP integration tests across `/login`, `/studio`, `/characters`, and `/episodes` with 200 OK responses.

---

### 2026-11-19 — Modularized App Codebase into Structured Domain Packages

Completed:
- **Clean Architecture & Directory Modularization**:
  - Reorganized root `app/` files into domain-driven subpackages:
    - **`app/auth/`**: `users.py`, `middleware.py`, `routes.py`, `security.py`, and `__init__.py`.
    - **`app/core/`**: `personas.py`, `prompts.py`, `catalog.py`, and `__init__.py`.
    - **`app/infra/`**: `storage.py` (AWS S3), `temporal.py` (Temporal orchestration), `logging.py` (Request & file logging framework), and `__init__.py`.
- **Zero-Breakage Compatibility Shims**:
  - Added lightweight backward-compatible shims at `app/auth_users.py`, `app/auth_middleware.py`, `app/auth_routes.py`, `app/security.py`, `app/personas.py`, `app/prompts.py`, `app/catalog.py`, `app/storage.py`, `app/temporal_setup.py`, and `app/logging_framework.py` so existing external imports and legacy code paths remain completely functional.
- **Verification & Smoke Tests**:
  - Verified 100% compilation across all modules (`0 errors`).
  - Audited module import trees across all 68 Python files (`0 failed imports`).
  - Executed automated HTTP smoke tests across `/login`, `/studio`, `/characters`, and `/episodes` with 200 OK responses.

---

### 2026-11-19 — Widened Character Modal & Constrained Textarea Resizing

Completed:
- **Widened Add Character Modal (`app/static/css/app.css`)**:
  - Increased `max-width` of `.char-modal-card` from `600px` to `820px` with enhanced horizontal padding (`padding: 2rem 2.25rem`).
  - Added `overflow-x: hidden` and `box-sizing: border-box` to prevent any horizontal scrollbar glitches.
- **Fixed Textarea Stretching Outside of Form**:
  - Locked horizontal resizing across all textareas and inputs: set `resize: vertical; min-width: 100%; max-width: 100%;`.
  - Textareas can now only be stretched vertically up and down without breaking out of the modal boundaries or creating horizontal layout shifts.

---

### 2026-11-19 — Added Red-Box Delete Button to Character Details Card for All Personas

Completed:
- **Repositioned Delete Button to Details Card (`app/templates/characters.html`, `app/static/css/app.css`)**:
  - Moved the character deletion button from the sidebar roster into the top-right corner of the **Character Details Panel** (`.char-editor-head`).
  - **Horizontal Alignment**: Positioned at the outmost right edge, parallel horizontally with the character's header name (`Chloe`, `Gary`, etc.).
  - **Vertical Alignment**: Sits comfortably above the media row (`Replace image` & `Upload audio` buttons).
  - **Visual Styling**: Rendered inside a solid red icon box (`background: #e11d48`, white trash can SVG icon, hover elevation with shadow).
- **Universal Character Deletion Support (`app/studio/characters.py`, `app/ui.py`)**:
  - Enabled deletion across all characters (including Gary, Linda, Chris, and Chloe) via a persistent `deleted_ids` registry in `characters/library.json`.
  - Maintained in-app confirmation modal with alert warning before completing the deletion.

---

### 2026-11-19 — Positioned Add Character Button to Top, Added Light Selection & Delete Workflow

Completed:
- **Repositioned Add Character Button**:
  - Moved the "Add New Character" dashed `+` button to the top of the **Cast Roster** sidebar, directly above the character list for immediate accessibility.
- **Enhanced Cast Selection Styling (`app/static/css/app.css`)**:
  - Added a light pink selection background (`rgba(255, 45, 138, 0.12)`), neon border (`var(--brand)`), and gentle shadow when selecting any character in the roster.
- **Character Deletion with In-App Confirmation Alert**:
  - Added a trash can delete icon button on the right edge aligned with the character's name for all custom characters.
  - Implemented an in-app confirmation modal (`#delete-character-modal`) with an alert badge, character name warning, and Delete/Cancel options.
  - Added `delete_character()` backend logic and `POST /ui/characters/{char_id}/delete` endpoint, safely preserving core founding characters (Gary, Linda, Chris, Chloe).
- **Mandatory Media Uploads**:
  - Marked Reference Portrait image and Voice Audio sample uploads as strictly mandatory (`required` attribute in HTML and backend validation).

---

### 2026-11-19 — Added Dynamic Character Upload & In-App Creation Modal in Characters Library

Completed:
- **Dynamic Character Persona Architecture (`app/studio/characters.py`)**:
  - Upgraded character library store (`characters/library.json`) to dynamically accommodate custom persona additions beyond the 4 founding characters (Gary, Linda, Chris, Chloe).
  - Implemented `create_character()` function with automated ID slugification, personality/psychological profiles, voice hints (speed, pitch, delivery tag), and media assignment.
  - Extended `save_character_image()` and `save_character_audio()` to support any newly added character IDs.
- **Roster UI Empty Box with Plus Icon (`app/templates/characters.html`, `app/static/css/app.css`)**:
  - Added an empty dashed card with a `+` icon box styled in Crash Out neon accents labeled "Add New Character" directly inside the Cast Roster sidebar.
- **In-App Creation & Confirmation Modal (`app/templates/characters.html`)**:
  - Built an in-app confirmation modal with smooth animated backdrop blur and escape/click-outside dismiss handlers.
  - Included fields for Character Name, Role, Archetype, Psychological Profile, Personality/Mannerisms, 9:16 Visual Prompt, reference portrait upload, voice audio sample upload, and delivery tag.
- **Backend Route & Automated Verification (`app/ui.py`)**:
  - Added `POST /ui/characters/new` supporting multipart file uploads for portraits and audio samples.
  - Tested creating a new character ("Officer Miller") end-to-end: verified creation, media persistence, instant roster display, and redirect to the character's editor view.

---

### 2026-11-19 — Resolved Login Credential Encoding & Enhanced In-App Alert UI

Completed:
- **Diagnosed and Fixed Login Failure**:
  - Investigated the login failure shown in the screenshot: the previous randomized password contained special character sequence (`=0DA$a`) which caused URL form decoding / copy-paste mismatch during browser submission.
  - Reset and verified the admin password in PostgreSQL (`users` table) with bcrypt hashing (`rounds=12`) using clean alphanumeric + standard special character format: `CrashOut2026!Admin`.
  - Executed automated full HTTP POST login test to `http://127.0.0.1:8000/login`, verifying HTTP 303 redirect and valid session & JWT cookies.
- **Enhanced In-App Error Alert UI (`app/templates/auth_login.html`, `app/static/css/app.css`)**:
  - Replaced the low-contrast browser alert with an enhanced, styled in-app banner featuring an SVG warning icon, prominent typography (`font-weight: 700`), neon pink glow, and smooth fade-in animation matching the Crash Out dark-suburban theme.
  - Eliminated repetitive browser form resubmission prompts by ensuring clear state handling on redirects.

---

### 2026-11-19 — Implemented Complete User Isolation & DB-Only Credentials

Completed:
- **Credentials Security (Database-Only Lookup)**:
  - Removed all hardcoded credentials and default environment fallbacks (`DEFAULT_LOGIN_*`) from the codebase and `.env`.
  - Configured login verification to strictly query PostgreSQL (`users` and `user_settings` tables).
  - Maintained `crashoutv.series@gmail.com` as the sole administrator in the database.
- **Multi-Tenant Private Workspace Isolation**:
  - Added `user_id` column to PostgreSQL `episodes` table and `Episode` Pydantic model (`app/state.py`).
  - Scoped custom catalog entries (`app/catalog.py`) with `user_id`.
  - Scoped Studio queue, episode list, finished library, and credit logs in `app/ui.py` and `app/studio/generation.py` to the logged-in `user.id`.
  - Assigned all existing 8 episodes and custom catalog rows to `crashoutv.series@gmail.com` (User ID `3`).
  - Verified with a simulated new user: new users start with **0 episodes, 0 queue items, and an empty clean dashboard** with complete isolation from other users.

---

### 2026-11-19 — Configured Production Admin Login Credentials (`crashoutv.series@gmail.com`)

Completed:
- **Created Production Admin User**:
  - Registered `crashoutv.series@gmail.com` with a randomized 20-character high-entropy secure password in PostgreSQL (`users` and `user_settings` tables).
  - Verified password hashing using bcrypt (`rounds=12`) and authenticated successfully.
- **Configured Seeding Fallback (`app/auth_users.py`)**:
  - Updated `DEFAULT_LOGIN_EMAIL`, `DEFAULT_LOGIN_PASSWORD`, and `DEFAULT_LOGIN_NAME` to respect environment variables and default to the new production admin credentials.
- **Auth Architecture Assessment**:
  - Evaluated session vs. JWT auth for the dashboard: confirmed session cookies remain optimal for limited browser users while JWT support is retained for programmatic API access.
  - Verified user data isolation scope: user credentials/Vidu keys are strictly user-scoped (`user_settings`), while episode catalog/scripts operate as a shared collaborative studio repository.

---

### 2026-11-19 — Project Structure Verification, Optimization & Clean-up

Completed:
- **Codebase Audit & Verification**:
  - Scanned all 240+ project files across `app/`, `characters/`, `assets/`, `docker/`, `migrations/`, and `outputs/`.
  - Verified syntax compilation across all 58 Python scripts without error (`py_compile`).
  - Verified module importability across all 57 `app.*` submodules without broken dependencies or missing modules.
  - Confirmed server startup and background workers initialize cleanly via `python run.py`.
- **Clean-up of Empty Folders & Stale Artifacts**:
  - Identified and safely removed the unused empty root folder `data/`.
  - Cleared transient `__pycache__` directories to keep the workspace clean and reduce disk clutter.
  - Verified no dangling 0-byte or orphaned temporary files exist across the repository.

---

### 2026-11-18 — Configured Production Let's Encrypt SSL & HTTPS for `admin.crashout.tv`

Completed:
- **DNS Verification**:
  - Verified DNS A record `admin.crashout.tv` resolving to public IP `54.166.201.137`.
- **Let's Encrypt Certificate Provisioning**:
  - Obtained official Let's Encrypt SSL certificates for `admin.crashout.tv` (`fullchain.pem` and `privkey.pem`).
  - Automated background renewal via certbot systemd timer.
- **Nginx Reverse Proxy & HTTPS Redirection (`/etc/nginx/conf.d/crashout.conf`)**:
  - Configured HTTP (port 80) server block to enforce permanent 301 redirection to `https://$host$request_uri`.
  - Configured HTTPS (port 443) server block with SSL certificates, DH parameters, 500MB upload support, and proxy pass to Uvicorn (`http://127.0.0.1:8000`).
- **Verification**:
  - Tested public HTTPS access via Python standard SSL client and curl: `https://admin.crashout.tv/login` returns **HTTP 200** with valid, trusted SSL handshake.

---

### 2026-11-18 — Synchronized 4 Finished Episodes to Live Server, AWS S3 & PostgreSQL

Completed:
- **Transferred 4 Complete Episodes to Live Server (`54.166.201.137`)**:
  - Packaged and transferred 4 full episodes to `/var/www/Crash_Out/outputs/`:
    1. **Ep #1**: `Episode 1 - TikTok Trends: November 2026 | The Crash Out`
    2. **Ep #2**: `Episode 2 - TikTok Trends: Generational Meltdown`
    3. **Ep #3**: `Episode 3 - The Strands Hint Breakdown`
    4. **Ep #4**: `Episode 4 - Fox News-Dominion Defamation Settlement`
  - Each episode includes complete 60s master MP4s (`merged_60s.mp4`), all 4 individual scene clips (`scene_1..4.mp4`), full 4-scene dialogue scripts, and 5 available concept pitches.
- **AWS S3 Synchronization**:
  - Uploaded all video assets and episode state documents to AWS S3 bucket `crashout-tv-media-assets-763928788903-us-east-1-an` under `episodes/<id>/`.
- **PostgreSQL Database Persistence**:
  - Persisted all concept pitches into the `generated_pitches` table in PostgreSQL.
  - Recorded 40 scene clips and master video assets with S3 URIs in the `video_assets` table.
- **Episode Management Library Activation**:
  - Updated `pipeline_index.json` and restarted `crashout.service`.
  - Verified `GET /episodes` lists all 4 published episodes with playable modal video players and episode record viewers.

---

### 2026-11-18 — Renamed Dashboard Hero CTA Button to AI Production Studio

Completed:
- **Button Label Update (`app/templates/dashboard.html`)**:
  - Renamed the hero banner primary CTA button from `Agent Studio` to `AI Production Studio` (`href="/studio?stage=0"`), keeping consistent terminology across the sidebar and dashboard.
- **Verification**:
  - Verified `GET /` with `TestClient` confirms the updated CTA label.

---

### 2026-11-18 — Tightened Heading Spacing across Characters, Episodes & Settings Pages

Completed:
- **Global Page Header Spacing Compacted (`app/static/css/app.css`)**:
  - Decreased `.page-shell` top padding from `1.25rem` to `0.5rem` to remove excess empty space above headings on Characters Library, Episode Management, Settings, and Credits pages.
  - Decreased `.page-head` bottom margin from `1.25rem` to `0.75rem`.
  - Added dedicated `.page-head h1` (`margin: 0 0 0.2rem; line-height: 1.2;`) and `.page-head p` (`margin: 0; line-height: 1.35;`) styling to eliminate browser margin voids between headings and taglines.
- **Verification**:
  - Verified `GET /characters`, `GET /episodes`, `GET /settings`, and `GET /credits` return HTTP 200 with compact styling.

---

### 2026-11-18 — Tightened Padding & Spacing on Credits Usage Page

Completed:
- **Tightened Header & Section Spacing (`app/templates/credits.html`)**:
  - Reduced container top padding (`padding-top: 0.5rem;`) to eliminate the excess empty space above "Credits Usage".
  - Eliminated browser default margins on `h1` (`margin: 0 0 0.2rem;`) and `p.muted` (`margin: 0;`).
  - Reduced `.page-head` bottom margin to `0.75rem` and `.dash-kpis` bottom margin to `1rem` to eliminate the vertical void between the description line and the KPI metric cards.
- **Verification**:
  - Verified authenticated `GET /credits` returns HTTP 200 with the compact spacing.

---

### 2026-11-18 — Removed Generation Queue Card from Animation & Rendering Page

Completed:
- **Removed Generation Queue (`app/templates/partials/workspace.html`)**:
  - Removed `{% include "partials/generation_queue.html" %}` from viewing stage 3 (`Animation & Rendering`).
  - The page now focuses exclusively on the video clips grid, clip preview player, individual clip regeneration, and the master episode assembly review.
- **Verification**:
  - Verified with `TestClient` that `/studio?stage=3` renders cleanly without the Generation Queue card or clip history side-panel (HTTP 200).

---

### 2026-11-18 — Restored Natural Hero Banner & Polished Unified Pipeline Cards

Completed:
- **Restored Standard Brand Hero (`app/templates/dashboard.html`)**:
  - Removed restrictive inline `height: 135px;` and forced crop overrides that had vertically squashed the hero banner down to an 85px slit with clipped character faces.
  - Restored standard stylesheet-driven `.brand-hero` and `.brand-hero-img` (220px height, `object-position: center 28%`) matching Image 2, ensuring Chris, Chloe, Gary, and Linda's faces and the copy/CTA are fully visible with natural padding.
- **Unified 4 Pipeline Metric Cards (`app/templates/dashboard.html`)**:
  - Standardized all 4 KPI numbers to brand hot-pink (`var(--brand-hot)`) with `.dash-kpi-value`, consistent with the reference design.
  - Aligned subtitles to match the exact counts (`{{ dashboard.studio_count }} in queue`, `{{ dashboard.scripting_count }} in draft & review`, `{{ dashboard.generating_count }} in video generation`, `{{ dashboard.published_count }} episodes published`) removing conflicting secondary counts.
- **Verification**:
  - Verified endpoint response with `TestClient` (HTTP 200).

---

### 2026-11-18 — Removed Meta-Strip (Viewing/Ep/HITL/Prod) from All Stages & Compacted Spacing

Completed:
- **Removed Meta-Strip HTML (`app/templates/partials/workspace.html`)**:
  - Removed the `meta-strip` containing `Viewing: <Stage> · Ep #<num>: <title> · HITL: <status> · Prod: <status>` across all agent steps.
- **Removed Empty Space (`app/static/css/app.css`)**:
  - Reduced `.stepper-bar` margin-bottom from `1.25rem` to `0.65rem` so there is no empty gap between the top navigation stepper bar and the stage content.
  - Set `.meta-strip { display: none !important; }` in CSS to prevent any cached rendering.
- **Verification**:
  - Ran `TestClient` verification across all studio stages (`/studio?stage=0..3`), confirming 200 OK and absence of meta-strip strings and empty voids.

---

### 2026-11-18 — Dashboard UI Redesign: Compact Hero Banner & Unified Agent Task Monitoring

Completed:
- **Compact Hero Banner (`app/templates/dashboard.html`)**:
  - Replaced oversized hero banner with a compact horizontal banner referenced directly from the production layout (~135px height, dark background `#111`, hot-pink 2px border with yellow glow, right-aligned Pearson family artwork at `object-position: right 25%`, and concise copy: "Production dashboard — Pipeline health, episode status, and credit usage." with an "Agent Studio" CTA button).
- **Consolidated 4 Pipeline KPI Cards with Agent Workflow Section (`app/templates/dashboard.html`)**:
  - Eliminated the redundant second KPI metrics row and merged the 4 core pipeline stages (`In Studio · A0`, `Scripting · A1`, `Generating · A3`, `Published · A4/A5`) directly inside the **Agent Workflow & Task Monitoring** panel.
  - Upgraded card design with top gradient accent strips (pink, orange, violet, emerald), agent ID pill badges (`A0`, `A1`, `A3`, `A4/A5`), status pills (`⚡ waiting approval`, `⚡ Vidu Q4 rendering active`, etc.), micro-descriptions, and clean typography conforming to the UI style rules (normal weight data, bold headers).
  - Preserved the dual-column "Channel Performance & Episode Analytics" and "Merchandising & Store Integration" sections with prominent "Coming Soon" indicators.
- **Verification**:
  - Verified authenticated endpoint rendering via `TestClient(app)` returning HTTP 200 with all cards, sections, and links validated.

---

### 2026-11-18 — Tightened Spacing in Stage 1 Pitch Review Header

Completed:
- **Reduced Top Margin on Back Button (`app/templates/partials/stages/stage_1.html`)**:
  - Removed excess `margin-top: 1.5rem` and `padding-top: 1.25rem`, reducing container margin to `margin-top: 0.25rem; margin-bottom: 0.75rem;`.
  - Scaled button padding to `padding: 0.45rem 1.1rem` with `font-size: 0.88rem`.
- **Reduced Header Padding (`app/templates/partials/stages/stage_1.html`)**:
  - Decreased `.panel-header` padding from `1.1rem 1.35rem` to `0.25rem 0.5rem 0.65rem` with `margin-bottom: 0.65rem`.
  - Compacted the "Approve pitch" button padding to `padding: 0.42rem 1.1rem`.

---

### 2026-11-18 — Fixed Agent 0 Row Selection Stuck on First Row

Completed:
- **Event Propagation Unblock (`app/templates/partials/stages/stage_0.html`)**:
  - Removed `onclick="event.stopPropagation();"` from `<td class="col-title">`, which was completely swallowing clicks on the episode title and preventing row selection.
  - Restricted `stopPropagation()` solely to active text input during title editing and the pencil rename icon.
  - Added instant row click visual feedback (`handleQueueRowClick`) and `data-select-url`.
- **Selection State Persistence & Hard Refresh Fix (`app/ui.py`)**:
  - Fixed `ui_studio()` which previously forced `_select_top_queue_item()` on every visit or refresh to `/studio?stage=0`. It now preserves the existing active episode in `state_manager`.
  - Updated `_studio_push_url` and selection responses to include `&episode={ep.id}` in `HX-Push-Url`, ensuring full browser URL synchronicity and refresh retention.
  - Verified with `TestClient` that selecting Gateway 1, 2, or 3 rows dynamically updates the top stepper menu bar and persists through browser page reloads.

---

### 2026-11-18 — Updated Agent 0 Daily Schedule from 6 AM UTC to 6 AM EST

Completed:
- **Temporal Schedule Update (`app/temporal_setup.py`)**:
  - Renamed schedule ID to `agent0-daily-6am-est`.
  - Updated cron specification `spec=ScheduleSpec(cron_expressions=["0 6 * * *"], time_zone_name="America/New_York")`.
- **APScheduler & Ingest Cadence (`app/trends/scheduler.py` & `.env.example`)**:
  - Changed default scheduler timezone from `UTC` to `America/New_York` (6:00 AM EST).
  - Updated environment variable defaults and docstrings.
- **UI & Mock Scheduler References (`app/ui.py`, `app/main.py`, `stage_0.html`)**:
  - Aligned the manual trigger and Stage 0 tooltip labels to 6:00 AM EST.

---

### 2026-11-18 — Agent 0 Row Selection with Dynamic Top Stepper Menu & Search Fix

Completed:
- **Agent 0 Row Selection & Top Stepper Gateway Adaptation (`app/templates/partials/stages/stage_0.html` & `app/static/css/app.css`)**:
  - Restored row selection visual feedback (`is-active selected`) with brand highlight background (`var(--brand-soft)`), pink inset indicator bar (`box-shadow: inset 3px 0 0 var(--brand)`), and hover states across the table.
  - Linked each row's selection to `data-status-gw` reflecting the episode's gateway state (`ep.current_gateway`). When a user selects a row, the active episode updates dynamically via HTMX partial swap (`#workspace`), immediately enabling/unlocking the top stepper bar menu stages (e.g. Scriptwriter for GW2+, Animation & Rendering for GW3+) corresponding to that episode's status.
- **Search Functionality Fix & Validation (`app/templates/partials/stages/stage_0.html`)**:
  - Validated and unified the search behavior with Episode Management:
    - Updated `filterQueueTable()` to perform real-time substring filtering across row text and editable input titles.
    - Synchronized pagination recalculation upon searching with dynamic match counts and clean "No episodes match" fallback.
    - Added both `onkeyup` and `oninput` handlers on `#queueTableSearch` and Search button click.

---

### 2026-11-18 — Enhanced Dashboard Aesthetic & Visual Polish

Completed:
- **Refined Dashboard Visual Presentation (`app/templates/dashboard.html`)**:
  - Elevated the dashboard design from basic layouts to a sleek studio aesthetic:
    - **Hero Banner**: Polished glass badge (`Autonomous Studio Hub · Live Multi-Agent System`), pulsing status beacon, deep gradient shade with character brand backdrop, and elevated buttons with glowing drop shadows.
    - **Agent Monitoring Bar**: Added top colored gradient indicator bars per agent (Pink for A0, Orange for A1, Purple for A3, Rose for A4, Emerald for A5), numeric agent index badges, live pulsing green radar indicator, and clear micro-status indicators for human interventions.
    - **KPI Counter Cards**: Introduced dedicated colored icon capsules (🎬, ✍️, ⚡, 🚀) with soft tinted borders, high-contrast typography, and subtle bottom dividing rules.
    - **Social Syndication Cards**: Added brand icon badges for YouTube Shorts (▶ red), TikTok (🎵 cyan), and Instagram Reels (📸 magenta) with 2-column engagement statistics and rounded badge tags.
    - **Merchandising Hub**: Enhanced store connection, apparel drop counter, and gross revenue tiles with consistent spacing, soft glass borders, and distinct status badges.

---

### 2026-11-18 — Studio Stepper Bar Rounded Corners & Content Alignment Fix

Completed:
- **Rounded Stepper Card & Contained Width (`app/static/css/app.css`)**:
  - Transformed `.stepper-bar` from a full-width flat strip with square corners into a rounded card matching the bottom content panel:
    - `border: 1px solid var(--border)`
    - `border-radius: var(--radius)` (10px rounded corners matching the panels)
    - `box-shadow: var(--shadow)`
    - `margin: 0 auto 1.25rem`
    - `overflow: hidden`
  - Removed excess outer horizontal padding from `.main-wrapper` (`padding: 0 0 2rem`) so the top stepper bar and the stage panels below align with the exact same left and right edges.
  - Adjusted `stage_0.html` top margin to sit cleanly below the rounded stepper bar without gaps.

---

### 2026-11-18 — Cleaned Dashboard to Only Display New Client-Requested Modules

Completed:
- **Cleaned Dashboard (`app/templates/dashboard.html`)**:
  - Removed old legacy sections:
    - Removed `Active episode`
    - Removed `Production mix`
    - Removed `Recent episodes` table
    - Removed `Studio queue` list
    - Removed `Revision notes` list
  - Kept only the new client-requested dashboard modules:
    - Top Hero Banner & Quick Entry to AI Production Studio
    - **Agent Workflow & Task Monitoring Bar**: Live tracking of autonomous agents (A0 Idea Gen & Waiting Approval, A1 Scriptwriting, A3 Video/Audio rendering, A4 Publishing, A5 Community & Seeding)
    - **KPI Metrics Cards**: Studio pipeline counters (In Studio, Scripting, Generating, Published)
    - **Channel Performance & Episode Analytics**: YouTube Shorts, TikTok, and Instagram Reels views & engagement tracking (with "Coming Soon" badges)
    - **Merchandising & Store Integration**: Store connection, merch catalog items, and total sales tracking per episode punchline (with "Coming Soon" badges)

---

### 2026-11-18 — Comprehensive Dashboard Overhaul per Client Specifications

Completed:
- **Agent Workflow & Task Monitoring Bar (`app/templates/dashboard.html` & `app/studio/generation.py`)**:
  - Implemented a prominent top monitoring bar showing each agent's current role and task status:
    - **A0 (Trend Research)**: Total ideas generated, and ideas awaiting human intervention/Gateway 1 approval.
    - **A1 (Scriptwriter)**: Total scripts ready and scripts actively in review (Gateway 2).
    - **A3 (Video & Audio / Animation & Rendering)**: Scene clips generated, Vidu Q4 API render status.
    - **A4 (Publishing)**: Multi-channel distribution status (Shorts, TikTok, Reels).
    - **A5 (Community & Seeding)**: Guerrilla seeding drafts (Reddit, TikTok comments).
- **Channel Performance & Episode Analytics (`app/templates/dashboard.html`)**:
  - Added dedicated card for Channel-by-Channel Successes (YouTube Shorts, TikTok, Instagram Reels) tracking views, likes, shares, and engagement rates.
  - Formatted with a visible **Coming Soon** badge until live platform metrics are connected.
- **Merchandising & Store Integration (`app/templates/dashboard.html`)**:
  - Added dedicated card for Merchandising tracking: Print-on-Demand store connection, catalog items, and sales conversion per episode punchline.
  - Marked with a **Coming Soon** badge until storefront webhook/API data is live.
- **Aggregated Backend Metrics (`app/studio/generation.py`)**:
  - Enhanced `studio_dashboard_snapshot()` to automatically compute agent-specific breakdown metrics (`agent_stats`).

---

### 2026-11-18 — Removed Sidebar Footer Text and Removed Credits KPI from Dashboard Top Cards

Completed:
- **Left Sidebar (`app/templates/base.html`)**:
  - Removed the `Crash Out` / `Pipeline workspace` footer labels from the bottom of the sidebar.
  - Pinned the **Credits Used** card cleanly at the very bottom of the sidebar.
- **Dashboard Top KPI Cards (`app/templates/dashboard.html` & `app/static/css/app.css`)**:
  - Removed the **Credits** card from the top KPI card row on the dashboard.
  - Adjusted the KPI grid layout from 5 columns to 4 columns (`In Studio`, `Scripting`, `Generating`, `Published`).

---

### 2026-11-18 — Relocated Credits Panel to Sidebar Bottom and Cleaned Up User Footer

Completed:
- **Sidebar Cleanup (`app/templates/base.html`)**:
  - Removed user name, email, and sign-out link from the left sidebar (now cleanly hosted on the top-right bar).
  - Shifted the **Credits Used** badge panel to the bottom of the sidebar pinned with `margin-top: auto`.
  - Pinned the minimal `Crash Out / Pipeline workspace` label cleanly below the credits panel.

---

### 2026-11-18 — Added Top Navigation Bar with User Profile and Sign Out

Completed:
- **Top Bar Component (`app/templates/base.html`)**:
  - Added a header bar (`.app-topbar`) spanning the top of the right main screen content area (`.app-main`).
  - Styled to match the light app theme with white background (`var(--surface)`), border-bottom (`var(--border)`), and soft drop shadow.
  - Aligned user information to the right side:
    - User avatar initial badge with brand pink accent.
    - User Name and Email (`Test`, `test@gmail.com`).
    - Vertical divider.
    - Styled `[⎋ Sign out]` button linking to `/logout`.
- **Content Padding (`app/templates/base.html`)**:
  - Wrapped page content in `.app-content-body` with comfortable padding (`1.5rem 1.75rem 2.5rem`) so all stage screens sit cleanly below the top bar.

---

### 2026-11-18 — Re-styled Delete Confirmation Modal to Match Light App Theme

Completed:
- **Theming Alignment (`app/templates/partials/stages/stage_0.html` & `app/templates/base.html`)**:
  - Replaced the dark background with the app's clean light surface theme:
    - Card Background: `var(--surface, #ffffff)`
    - Border: `1.5px solid var(--border, #e8d5e0)` with soft pink-tinted drop shadow `0 16px 40px rgba(40, 8, 28, 0.18), 0 2px 8px rgba(255, 45, 138, 0.08)`.
    - Backdrop: `rgba(26, 18, 32, 0.45)` with `backdrop-filter: blur(4px)`.
    - Headings & Text: `var(--text, #1a1220)` for title, `var(--muted, #6b5a66)` for description.
    - Danger Badge: Soft rose background (`#fff1f2` with `#fecdd3` border) and crimson icon (`#be123c`).
    - Cancel Button: `var(--surface)` with `var(--border)` outline and `var(--text)` label.
    - OK Button: Solid crimson `#be123c` with shadow `0 2px 6px rgba(190, 18, 60, 0.25)`.

---

### 2026-11-18 — Dedicated Inline Delete Confirmation Modal in Episode Queue

Completed:
- **Added Self-Contained Delete Modal (`app/templates/partials/stages/stage_0.html`)**:
  - Embedded `#queue-delete-modal` directly within the `stage_0.html` partial to guarantee that deleting an episode always displays the custom-styled dark theme modal with backdrop blur.
  - Modal features:
    - Trash/delete icon in red circle badge.
    - Title: **Delete Episode?**
    - Dynamic message with target episode title: `Delete “{display_title}” from the queue? This cannot be undone.`
    - **Cancel** button (closes modal) and **OK** button (submits deletion request via HTMX to `/ui/queue/{id}/delete` with outerHTML workspace swap).
    - Backdrop click-to-close handler.
  - Linked the trash icon action directly via `onclick="openDeleteConfirmModal('/ui/queue/{{ card.id }}/delete', '...')"` so it opens reliably on every click.

---

### 2026-11-18 — Replaced Native Browser Confirm with Styled Delete Modal Dialog

Completed:
- **Redesigned Confirmation Modal (`app/templates/base.html`)**:
  - Replaced the browser native `hx-confirm` prompt with a dark-themed, styled modal confirmation dialog (`#app-confirm-dialog`).
  - Added warning icon, clear title ("Delete Episode?"), subtitle, a **Cancel** button, and an **OK** button styled with red destructive highlight (`.btn-danger`).
- **Updated Episode Delete Action (`app/templates/partials/stages/stage_0.html`)**:
  - Replaced `hx-confirm` with `data-confirm-delete="true"`, `data-delete-url`, and `data-delete-title`.
- **Integrated Modal Handler (`app/static/js/ui.js`)**:
  - Tied delete trigger to `openDeleteConfirm(url, title)`.
  - On confirming via **OK**, HTMX posts to `/ui/queue/{id}/delete` and updates the workspace seamlessly.
  - Exposed `window.closeDeleteConfirm()` for the **Cancel** button and click-outside dismissal.

---

### 2026-11-18 — Remove "Agent <N>" Prefixes from Stage Labels and Panel Headers

Completed:
- **Cleaned Stepper Labels (`app/ui.py`)**:
  - Removed "Agent 0:", "Agent 1:", "Agent 3 –", "Agent 4 –", and "Agent 5 –" from `STAGE_LABELS`.
  - Stages are now cleanly named:
    - `Trend Research & Approve Pitch`
    - `Scriptwriter`
    - `Animation & Rendering`
    - `Publishing & Merchandising`
    - `Community & Promotion`
- **Cleaned Stage Panel Headers & Descriptions (`app/templates/partials/stages/`)**:
  - Updated `stage_0.html`, `stage_1.html`, `stage_2.html`, `stage_3.html`, `stage_4.html`, and `stage_5.html` to remove the "Agent <N>" prefix from all `panel-title` headers and `panel-desc` intros.

---

### 2026-11-18 — Scriptwriter Scene Regenerate Visibility & Agent 3 Clip Regeneration

Completed:
- **Scriptwriter Regenerate Button Visibility (`app/templates/partials/script_scene_block.html`)**:
  - Hid the "Regenerate this clip" button and "Clip ready" badge on the Scriptwriter page (Stage 2) prior to Agent 3 running.
  - The button and badge only appear after Agent 3 has rendered the scene clip (`ep.current_gateway >= 3` and `clip_ready`).
- **Prevent Premature Sibling Video Render Hydration (`app/ui.py`)**:
  - Updated `_hydrate_renders_from_siblings(ep)` to only copy rendered scene/master videos when `ep.current_gateway >= 3`, preventing newly created or Gateway 1/2 episodes from prematurely inheriting sibling clips and badges.
- **Agent 3 Clip Regeneration Prompt Verification (`app/templates/partials/stages/stage_3.html`, `app/main.py`)**:
  - Verified each clip card in Agent 3 (`Agent 3 – Animation & Rendering`) has its own `Regenerate` button calling `/ui/video/generate-scene/{scene_id}`.
  - Verified `generate_single_scene` retrieves the exact prompt for that clip (`source_prompt` / `vidu_prompt`) from `ep.script["scenes"]` to regenerate that specific clip.

---

### 2026-11-18 — Re-label Agents 3, 4, and 5 in Studio Stepper and Panels

Completed:
- **Updated Stepper Labels & Marks (`app/ui.py`)**:
  - Re-labeled Stage 3: `Agent 3 – Animation & Rendering` (stepper mark updated from `A2/3` to `A3`).
  - Re-labeled Stage 4: `Agent 4 – Publishing & Merchandising` (stepper mark `A4`).
  - Re-labeled Stage 5: `Agent 5 – Community & Promotion` (stepper mark `A5`).
- **Updated Stage Panels (`app/templates/partials/stages/stage_3.html`, `stage_4.html`, `stage_5.html`)**:
  - Panel header titles and descriptions updated to match the new naming across the production studio.


---

### 2026-11-18 — Agent 0 Search Placeholder & Horizontal Baseline Row Alignment

Completed:
- **Search Placeholder (`app/templates/partials/stages/stage_0.html`)**:
  - Updated the search input placeholder to **`"Search by Episode..."`**.
  - Validated client-side and dynamic multi-word search matching across titles, IDs, inputs, and statuses.
- **Horizontal Baseline Alignment & Action Button Wrap Fix (`app/templates/partials/stages/stage_0.html`)**:
  - Removed the `.row-actions` class from the table cell and replaced it with a dedicated container having `white-space: nowrap; width: 100%; display: flex; align-items: center; justify-content: flex-end;` so action items never wrap or break upwards.
  - Increased the Actions column header and cell width to `180px`.
  - Harmonized `vertical-align: middle;` across all table columns (`Sr. No.`, `Title`, `Pitch`, `Status`, `Actions`) with `align-items: center;` on the title row form. All columns now stay centered on the same horizontal baseline across the entire row.


---

### 2026-11-18 — Rename Navigation Button to Back to Episode List

Completed:
- **Button Label Updated (`app/templates/partials/stages/stage_1.html`)**:
  - Changed the top navigation button label and title attribute from `"Back to Video List"` to **`"Back to Episode List"`**.


---

### 2026-11-18 — Fix Table Row Vertical Alignment on Multi-Line Titles

Completed:
- **Consistent Top Vertical Alignment (`app/templates/partials/stages/stage_0.html`)**:
  - Added `vertical-align: top;` to all `<td>` table cells (`col-num`, `col-title`, `Pitch`, `Status`, `Actions`).
  - Previously, `vertical-align: middle;` caused adjacent columns (`Sr. No.`, `Pitch`, `Status`, `Actions`) to drift downward toward the middle when an episode title wrapped across two or more lines, distorting the horizontal baseline.
  - Now, all columns remain cleanly anchored to the top of their respective row regardless of how many lines the title spans.


---

### 2026-11-18 — Grey Out Select Buttons & Approve Button Once Pitch is Approved

Completed:
- **Greyed-Out Approve Pitch Button (`app/templates/partials/stages/stage_1.html`)**:
  - When viewing an already approved episode (`current_gateway >= 2`), the top-right `Approve pitch` button transitions into a disabled, greyed-out button (`opacity: 0.5; cursor: not-allowed; filter: grayscale(1); background: #9ca3af; border-color: #9ca3af; color: #ffffff;`) with text `✓ Pitch Approved`.
- **Greyed-Out Select Buttons for Other Pitch Cards (`app/templates/partials/stages/stage_1.html`)**:
  - On the chosen approved pitch card, the button displays `✓ Approved`.
  - On all other pitch cards, the `Select` button is disabled and greyed out (`opacity: 0.45; filter: grayscale(1); cursor: not-allowed; border: 1px solid #d1d5db; color: #9ca3af; background: #e5e7eb;`), making it unmistakably clear that other pitches cannot be selected.


---

### 2026-11-18 — Polish Agent 0 Table Alignment, Multi-Word Search, Status No-Wrap & Pitch Approval Grey-Out

Completed:
- **Right-Aligned Actions Column (`app/templates/partials/stages/stage_0.html`)**:
  - Shifted the table action buttons (`Open →` and trash delete) flush to the right edge with `margin-left: auto; justify-content: flex-end;`.
- **Status Column Single-Line (`app/templates/partials/stages/stage_0.html`)**:
  - Allocated a dedicated `220px` width with `white-space: nowrap;` on the status cell and badge so statuses like `"Waiting Pitch Approving"` and `"Waiting for Scriptwriting"` never break into multiple lines.
- **Table Pagination**:
  - Enforced `queuePageSize = 10` rows per page with page numbers and next/prev controls.
- **Multi-Word Search (`app/templates/partials/stages/stage_0.html`)**:
  - Upgraded `filterQueueTable()` to tokenize queries by word (matching the episode management search algorithm). Users can type multiple words in any order to find matching titles, IDs, and statuses instantly.
- **Pitch Approval Grey-Out Only When Actually Approved (`app/templates/partials/stages/stage_1.html`, `app/ui.py`)**:
  - Refined `is_approved` definition to strictly check gateway advancement (`current_gateway >= 2` or active non-draft/waiting status) so unapproved episodes never show cards greyed out upon first opening.
  - Cards now display full interactivity when opened in Gateway 1 and only grey out the unselected cards after clicking the **Approve pitch** button on the right.


---

### 2026-11-18 — Step-by-Step Production Statuses in Video Queue Table

Completed:
- **Human-Friendly Step Status Mapping (`app/ui.py`)**:
  - Implemented `_format_queue_status(ep)` to format episode statuses based on current production milestones instead of raw internal database codes (`WAITING_GATEWAY_1`, etc.):
    - **Step 1 (Pitches not approved yet)**: `"Waiting Pitch Approving"`
    - **Step 2 (Pitch approved, in scripting)**: `"Waiting for Scriptwriting"`
    - **Step 3 (Script approved, video generating)**: `"Waiting for Video Generation"`
    - **Step 4 (Merch package review)**: `"Waiting for Merch Sign-Off"`
    - **Step 5 (Publishing sign-off)**: `"Waiting for Publishing Sign-Off"`
    - **Completed**: `"Published"`
  - Updated both `_catalog_cards()` and `_studio_queue_cards()` to use `_format_queue_status` so the Agent 0 video list table always displays clear, friendly step labels.


---

### 2026-11-18 — Pitch Approval Lock: Grey Out Unselected Pitches & Prevent Modifications

Completed:
- **Locked Pitch State UI (`app/templates/partials/stages/stage_1.html`)**:
  - Once a pitch is approved (i.e. `ep.current_gateway >= 2` or `ep.script` is populated):
    - Replaced the `Approve pitch` button with a clean `✓ Pitch Approved` badge.
    - Marked the chosen card with an `✓ Approved` badge and glowing border.
    - All other non-selected pitch cards are greyed out (`opacity: 0.42; filter: grayscale(1); background: #f3f4f6; pointer-events: none; cursor: not-allowed;`).
    - The `Select` buttons on unapproved cards are replaced with disabled `Locked` states.
    - All text areas and inputs on pitch cards become `readonly disabled` to prevent post-approval edits.
- **Backend Guardrails (`app/ui.py`)**:
  - In `ui_select_concept` and `ui_update_concept`, added validation to check if `ep.current_gateway >= 2` or `bool(ep.script)`. Any attempt to select another pitch or edit fields on an approved episode is rejected with `"Pitch already approved and locked."`.


---

### 2026-11-18 — Polish Agent 0 Table: Title Text Wrapping, Live Search, Descending Sr. No. & Uncolored First Row

Completed:
- **Episode Title Text Wrapping (`app/templates/partials/stages/stage_0.html`)**:
  - Replaced the single-line input field in the table display with a text span (`.ep-title-text`) with `word-break: break-word; overflow-wrap: break-word; line-height: 1.45;` so long episode titles wrap naturally across multiple lines instead of being cut off or clipped.
  - Retained inline editing: clicking the pencil icon ✎ or double-clicking the title text swaps into an editable `<input>` and focuses it immediately.
- **Search Table Fix (`app/templates/partials/stages/stage_0.html`)**:
  - Updated `filterQueueTable()` to search both text content and any inner input values (`text += ' ' + inp.value`) as well as episode IDs.
  - Tied filter execution to pagination recalibration so search filtering instantly updates the table view, page counts, and matches.
- **Descending Sr. No. (`app/templates/partials/stages/stage_0.html`)**:
  - Displayed `card.list_number or (catalog_cards|length - loop.index0)` so rows count downwards (e.g. 6, 5, 4, 3, 2, 1) matching the newest-first order of episodes.
- **Removed First Row Highlight Color (`app/templates/partials/stages/stage_0.html`)**:
  - Removed `is-active` background color from the active/top row in the table (`background: transparent;`). All rows now share uniform, clean table styling without an aggressive background tint.


---

### 2026-11-18 — Mockup Queue Workflow: Return to Table & Require Manual Pitch Selection

Completed:
- **Mockup Return Destination (`app/ui.py`)**:
  - In `ui_mockup_queue_scheduler`, updated the HTMX response to render `viewing_stage=0` instead of `viewing_stage=1`.
  - When the user clicks **Mockup**, the newly generated episode (`EP-<serialnumber>-<YYYYMMDD>`) is added directly to the Agent 0 queue table and remains on the video list view so the user sees the newly added episode at the top of the table.
- **No Default Selected Pitch Card (`app/ui.py`)**:
  - Removed auto-selection of the first pitch card (`ep.selected_concept = None`).
  - Updated `_selected_concept_index(ep)` to return `None` (rather than defaulting to 0) when no concept has been chosen yet.
  - Updated `ui_approve_gateway_1` to require an explicit human selection before approving (`"Please select one of the pitches first before approving"`).
  - Users can now review all 5 pitch cards, click **Select** on their chosen angle, and then approve it for scripting.


---

### 2026-11-18 — Polish Back Button Spacing, Newest-First Queue Sorting & EP-Number-Date Episode Naming

Completed:
- **Consistent Top Padding on Pitch Approval Page (`app/templates/partials/stages/stage_1.html`)**:
  - Added matching top padding and margin (`margin-top: 1.5rem; padding-top: 1.25rem;`) to the `Back to Video List` container so it aligns with other pages and doesn't sit pressed against the stepper bar.
- **Queue Table Sorting Newest First (`app/ui.py`)**:
  - Updated `_studio_queue_cards()` to sort all entries in reverse chronological order (`list_number` / episode number descending, with creation timestamp fallback), guaranteeing that newest video items always show on top.
- **Episode Naming Scheme `EP-serialnumber-date` (`app/studio/naming.py`, `app/state.py`, `app/ui.py`)**:
  - Replaced the datetime stamp naming (`Episode_YYYYMMDD_HHMMSS`) with the concise format: `EP-<serialnumber>-<YYYYMMDD>` (e.g. `EP-4-20261118`).
  - Updated `studio_base_name` and regex `_STAMP_RE` to match both new `EP-\d+-\d{8}` format and legacy titles seamlessly.
  - Linked episode creation across `state_manager.create_episode`, catalog selection, and mock runs to pass the resolved episode serial number into `make_studio_episode_name`.


---

### 2026-11-18 — Polish Pitch Approval Header & Add Agent 0 Table Pagination & Top Padding

Completed:
- **Pitch Approval Header Polish (`app/templates/partials/stages/stage_1.html`)**:
  - Styled **`← Back to Video List`** with the solid primary button style (`class="btn btn-primary"`, padding `0.55rem 1.25rem`), making it match the visual weight and styling of the `Approve pitch` button.
  - Added full text wrapping (`word-break: break-word; overflow-wrap: break-word; line-height: 1.4;`) to the episode title heading so long titles wrap cleanly without clipping or pushing the `Approve pitch` button out of horizontal alignment.
- **Agent 0 Table Spacing (`app/templates/partials/stages/stage_0.html`)**:
  - Added dedicated top margin and padding (`margin-top: 1.5rem; padding-top: 1.25rem;`) to the Agent 0 stage queue container so it is no longer pressed flush against the top stepper.
- **Client-Side & HTMX Table Pagination**:
  - Implemented responsive pagination controls below the queue table:
    - Showing entries counter (e.g. `Showing 1 to 10 of 12 entries`).
    - `Previous` and `Next` buttons with disabled boundaries.
    - Page number buttons with active primary state.
    - Integrated with live table search so filtering automatically recalculates total pages and active page indices.
    - Re-attaches seamlessly upon HTMX swapping.

---

### 2026-11-18 — Refactor Pitch Approval Header & Move Back Button Outside Card

Completed:
- **Moved Back Button Outside Card**: Moved the **`← Back to Video List`** button above and outside the pitches card in `app/templates/partials/stages/stage_1.html`.
- **Card Header Clean Alignment**:
  - Removed `"Agent 0: Trend Research and Approve Pitch"` and the instruction subtext from the card header.
  - Positioned the **Episode Title** (`{{ ep.title }}`) on the left as the sole prominent heading (`font-size: 1.25rem; font-weight: 700;`).
  - Positioned the **`Approve pitch`** button on the right, horizontally aligned and equal in line with the title.

---

### 2026-11-18 — Remove Meta-Strip from Agent 0 & Add Back Navigation in Pitch Workspace

Completed:
- **Cleaned Top Header (Removed Meta-Strip)**:
  - Removed the `Viewing: Agent 0... · Ep #... · HITL... · Prod...` meta-strip from Agent 0 (stages 0 & 1) in `app/templates/partials/workspace.html`. The workspace remains clean and uncluttered.
- **Added Back to Video List Button**:
  - In `app/templates/partials/stages/stage_1.html`, placed a prominent **`← Back to Video List`** button in the header right next to the title **`Agent 0: Trend Research and Approve Pitch`**.
  - Clicking `Back to Video List` seamlessly transitions back to the Agent 0 video table (`/studio?stage=0`) via HTMX with outerHTML swap.

---

### 2026-11-18 — Direct Studio Pitch Review Page Navigation from Table

Completed:
- **Direct Full Page Pitch Navigation**:
  - Replaced the modal popup on the table's `💡 Pitch` button with direct HTMX navigation (`/ui/episodes/{id}/pitches` and `/ui/catalog/{id}/pitches`).
  - Clicking `💡 Pitch` now directly transitions into the full **Agent 0: Trend Research and Approve Pitch** workspace (Stage 1 concept review view with selectable and editable pitch cards, consensus ratings, and Gateway 1 pitch approval), exactly like entering a newly generated episode from the queue.
  - Cleaned up the leftover modal DOM elements from `stage_0.html`.

---

### 2026-11-18 — Polish Agent 0 Table Alignment & Rename Stage to Agent 1: Scriptwriter

Completed:
- **Agent 1 Renaming**:
  - Renamed the script stage to **`Agent 1: Scriptwriter`** across `app/ui.py` (`STAGE_LABELS[2]`), top pipeline stepper, and `app/templates/partials/stages/stage_2.html`.
- **Agent 0 Table Alignment & Symmetric Styling**:
  - Re-aligned the Agent 0 queue table to match the clean design system of Episode Management:
    - Added the brand-themed header styling (`var(--brand-soft)` background, `2px solid rgba(255, 45, 138, 0.25)` border, bold uppercase `var(--brand-ink)` text).
    - Fixed explicit column widths: `width: 80px` (Sr. No.), flexible `col-title` (Title), `width: 140px` (Pitch), `width: 150px` (Status), and `width: 180px; text-align: right;` (Actions).
    - Added symmetric padding (`0.85rem 1rem`) across all `<th>` and `<td>` cells.
    - Set the row actions container to `display: inline-flex; justify-content: flex-end; gap: 0.4rem; white-space: nowrap;` for flush right alignment.

---

### 2026-11-18 — Remove Duration Column & Enhance Inline Title Editing Responsiveness

Completed:
- **Backend Task Stopped**: Stopped the background server task spawned previously, keeping only the user's terminal backend process active.
- **Removed Duration Column**: Removed the `"Duration"` column header and cell from the Agent 0 queue table in `app/templates/partials/stages/stage_0.html`, streamlining the table view to `Sr. No.`, `Title`, `Pitch`, `Status`, and `Actions`.
- **Title Editing Robustness**:
  - Replaced the text character pencil with a high-definition SVG vector pencil icon with direct click handler `startTitleEdit(...)`.
  - Added double-click (`ondblclick="startTitleEdit(this)"`) directly on the title input for instant editing without requiring precise icon clicks.
  - Ensured `readonly` state toggles off, cursor changes, and input focuses and selects title text immediately.

---

### 2026-11-18 — AI Production Studio Sidebar Renaming, Agent 0 Table Pitch Column & Inline Title Editing

Completed:
- **Sidebar Nav Renaming**:
  - Renamed `"Agent Studio"` to **`AI Production Studio`** in `app/templates/base.html`, `dashboard.html`, `episodes.html`, and `credits.html`.
- **Search Option Moved Above Table**:
  - Moved the search bar out of the table body/card and into the top header actions of the **Agent 0: Trend Research and Approve Pitch** card, matching the symmetric layout used across Episode Management.
- **Agent 0 Table Pitch Column**:
  - Added a dedicated **`Pitch`** column to the queue table in `app/templates/partials/stages/stage_0.html`.
  - Added an accessible **`💡 Pitch (N)`** button in every row, opening a full-fidelity modal that presents all 5 generated friction intersection pitch cards (Headline, Consensus score, Sensitivity flag, Youth & Cultural Hook, Crash-Out angle, and Merch punchline) with a direct action button to open in studio.
- **Inline Title Editing from Table**:
  - Added an inline pencil icon edit action in the **Title** column of the Agent 0 table.
  - Clicking the pencil enables inline editing with Enter/blur submit via HTMX (`/ui/episodes/{id}/rename` or `/ui/queue/{id}/rename`), updating both the episode record and custom catalog item titles without page reloads.

---

### 2026-11-18 — Consolidate Agent 0 Pipeline & Relabel to Trend Research and Approve Pitch

Completed:
- **Agent Studio Pipeline Alignment**:
  - Relabeled Stage 0 to: **`Agent 0: Trend Research and Approve Pitch`** in `app/ui.py` (`STAGE_LABELS` and `STAGE_MARKS`), `stage_0.html`, and `stage_1.html`.
  - Removed separate `"Agent 1 (Pitches)"` tab from the top pipeline stepper in `app/templates/partials/workspace.html`, unifying the discovery and pitch approval process cleanly under **`Agent 0: Trend Research and Approve Pitch`**.
  - Updated subsequent pipeline marks and labels to match the specification (`A0`, `A1 (Script)`, `A2/3 (Video)`, `A4 (Publish)`, `A5 (Seeding)`).
- **Files Modified**:
  - `app/ui.py`: Updated `STAGE_LABELS` and `STAGE_MARKS`.
  - `app/templates/partials/workspace.html`: Skipped redundant `num == 1` in stepper and highlighted Agent 0 when viewing pitch cards.
  - `app/templates/partials/stages/stage_0.html`: Updated panel header to `Agent 0: Trend Research and Approve Pitch`.
  - `app/templates/partials/stages/stage_1.html`: Updated panel header and description to `Agent 0: Trend Research and Approve Pitch`.

---

### 2026-11-18 — Revert Sidebar Menu Font Size to 0.98rem

Completed:
- **Font Size Reversion**: Reverted `.nav-link` font size to **`0.98rem`** (`padding: 0.7rem 0.85rem`) in `app/static/css/app.css` as requested.

---

### 2026-11-18 — Adjust Sidebar Menu Font Size to 0.95rem

Completed:
- **Font Size Fine-Tuning**: Adjusted `.nav-link` font size to exactly **`0.95rem`** (`padding: 0.68rem 0.82rem`) in `app/static/css/app.css` for optimal visual balance with the vector SVG icons.

---

### 2026-11-18 — Polish Sidebar Menu Font Size & Vector SVG Icons

Completed:
- **Typography & Font Size**:
  - Increased `.nav-link` font size from `0.9rem` to `0.98rem` with `font-weight: 600` and enhanced spacing (`padding: 0.7rem 0.85rem; gap: 0.75rem`).
- **High-Definition Vector SVG Icons**:
  - Replaced generic Unicode characters (`◆`, `▶`, `☰`, `◎`, `⚙`) with clean, responsive vector SVG icons in `app/templates/base.html`:
    - **Dashboard**: Layout grid icon (`<rect>` layout).
    - **Agent Studio**: Play / studio production icon (`<polygon points="6 3 20 12 6 21 6 3">`).
    - **Episode Management**: Video episode / clapperboard tv icon (`<rect>` with screen antenna).
    - **Characters Library**: Multi-character user group avatar icon.
    - **Settings**: Refined mechanical gear icon.
  - Sized icons to `1.3rem` with `stroke-width="2"` and crisp SVG rendering.

---

### 2026-11-18 — Switch Episodes Table Review Action to Approved Pitch

Completed:
- **Button Change (`app/templates/episodes.html`)**: Replaced the `📜 Script` button in the Episode Management table with **`💡 Pitch`** (`onclick="openPitchModal('pitch-modal-{{ ep.id }}')"`).
- **Approved Pitch Review Modal**:
  - Clicking `💡 Pitch` opens a modal displaying the exact pitch concept approved by the client that originated the episode:
    - Headline and consensus score (`/10`) with `Approved Pitch` badge.
    - **Youth & Cultural Hook** breakdown.
    - **Story Premise & Crash-Out Angle**.
    - **Proposed Merch Trigger** and Trend Sources.
    - Direct action button to jump into the episode record (`View Generated Episode →`).

---

### 2026-11-18 — Standardize Characters Library Page Header

Completed:
- **Header Symmetry (`app/templates/characters.html`)**:
  - Replaced the nested sidebar `<h2>` inside `.char-nav` with the standard top-level `.page-head` container matching Episode Management, Settings, and Credits.
  - Added symmetric `<h1>Characters Library</h1>` with subtitle and browser title `<title>Characters Library — Crash Out</title>`.
  - Replaced inner nav title with clean `<h3>Cast Roster</h3>` to maintain clean visual hierarchy.

---

### 2026-11-18 — Restore Episode Management Page Titles & Breadcrumbs

Completed:
- **Page Head & HTML Title (`app/templates/episodes.html`)**: Restored the page heading `<h1>Episode Management</h1>` and page title `<title>Episode Management — Crash Out</title>`.
- **Breadcrumb Link (`app/templates/episode_record.html`)**: Restored the back link to `<a href="/episodes">← Episode Management</a>` to maintain full naming parity with the sidebar.

---

### 2026-11-18 — Restore Sidebar Nav Label to Episode Management

Completed:
- **Sidebar Nav Label**: Restored the navigation menu item label in `app/templates/base.html` back to **`Episode Management`** (`<span class="nav-label">Episode Management</span>`), matching the original menu structure.

---

### 2026-11-18 — Refactor Sidebar Brand to Fitted Logo Only

Completed:
- **Removed Brand Text**: Removed the text container (`<div class="brand-title"><span class="brand-title-crash">CRASH</span> <span class="brand-title-out">OUT</span></div>` and subtitle) from the application sidebar in `app/templates/base.html`.
- **Fitted Logo to Sidebar Width**:
  - Centered and scaled the brand badge logo (`.brand-logo-full`, `max-width: 140px`) to fit the sidebar width.
  - Kept the gold and neon pink circular badge styling with subtle glow shadows to make the logo prominent at the top of the sidebar.

---

### 2026-11-18 — Reposition Search Control to Page Header

Completed:
- **Relocated Search Bar**: Moved the search bar completely out of the `.table-card` wrapping and placed it in `.page-head-actions` on the right side of the page header across from the **Episodes** title.
- **Table Card Integrity**: The `.table-card` now solely contains the clean, themed `<table class="data-table">` without any wrapper containers or extra borders above the column headers.
- **Search Filtering**: Restored real-time search filtering (`filterEpisodesTable`) on keyup/button click.

---

### 2026-11-18 — Remove Episodes Table Search & Apply Brand Theme to Table Headers

Completed:
- **Removed Search Bar**: Removed the top search bar (`#episodesTableSearch`) and its unused search filtering function from `app/templates/episodes.html`.
- **Applied Brand Theme to Column Titles**: Styled the `<thead>` of `episodesDataTable` to match the brand color scheme:
  - Header background: `var(--brand-soft)` (subtle pink tint matching active navigation/theme accents).
  - Header text color: `var(--brand-ink)` (deep brand magenta) with `font-weight: 700`, `letter-spacing: 0.05em`, and uppercase styling.
  - Border separator: `2px solid rgba(255, 45, 138, 0.25)`.

---

### 2026-11-18 — Fix Episodes Table Alignment & Column Widths

Completed:
- **Table Column Alignment**:
  - Moved the hidden quick-script modals outside of the `<table>` element to prevent DOM insertion from distorting column geometry and flex layout calculations.
  - Set explicit column widths (`width: 80px` for Sr. No., `width: 140px` for Status, `width: 220px; text-align: right;` for Actions, and flexible width for Title).
  - Aligned the Actions cell contents to `justify-content: flex-end; white-space: nowrap;`, ensuring the **`📜 Script`** and **`Open Record →`** buttons align flush with the table header and stay cleanly within the table boundaries.

---

### 2026-11-18 — Polish Script Review & Clip Titles in Episodes View

Completed:
- **Clean Section Title & Subtitle**:
  - Replaced `"Agent 2 — Review script & prompts"` and its description with clean client-facing copy:
    - **Title**: `Script Review`
    - **Subtitle**: `Review the 4-clip episodic script and character prompts before inspecting the rendered video clips.`
  - Synchronized across both the **Episode Record** page (`app/templates/episode_record.html`) and the **Episodes Modal** (`app/templates/episodes.html`).
- **Video Clips Header & Simplified Clip Names**:
  - Changed section header from `Scene clips` to **`Video Clips`** across `episode_record.html` and `stage_3.html`.
  - Simplified the clip titles on video cards from `Clip 1 · Hook & Setup` to clean **`Clip 1`**, **`Clip 2`**, **`Clip 3`**, and **`Clip 4`**.

---

### 2026-11-18 — Agent 2 Parity for Script Review & UI Cleanups in Episodes

Completed:
- **Agent 2 Parity for Script Review**:
  - Updated the script review in both the **Episode Record** page (`app/templates/episode_record.html`) and the **Episodes Modal** (`app/templates/episodes.html`) to match Agent 2's layout:
    - 4 horizontal clip tabs (**Clip 1**, **Clip 2**, **Clip 3**, **Clip 4**) with timeline durations (`00:00 - 00:08 · 8s`, etc.).
    - Interactive tab selection switching between panels.
    - Script prompt editor card with character count badge, clip ready badge, and full generation prompt text.
- **Removed "EPISODE MANAGEMENT" & "#1 ·"**:
  - Renamed nav and page title from "Episode Management" to "**Episodes**" in `base.html`, `episodes.html`, and breadcrumbs in `episode_record.html`.
  - Removed `#1 ·` prefix from the title in `episode_record.html`.
- **Clip Naming Parity on Video Cards**:
  - Changed video card labels from `Scene 1`, `Scene 2` to `Clip 1`, `Clip 2`, `Clip 3`, `Clip 4` across `stage_3.html` and `episode_record.html`.

---

### 2026-11-18 — Episode Management Script-First Client Review Flow

Completed:
- **Episode Record Script-First Structure (`app/templates/episode_record.html`)**:
  - Reordered the record page hierarchy so clients review the full **Episode Script & Character Dialogue** *first* at the top of the page before scrolling to the rendered scene clips and the full merged master video.
  - Formatted scene cards showing Scene Number, Title, Timeline range, Duration, Primary Character, Visual Action/Camera Cue callout, and dialogue quotes.
- **Episodes Management Table Quick Script Modal (`app/templates/episodes.html`)**:
  - Added a `📜 Script` button alongside `Open Record →` in the **Episode Management** library table.
  - Clicking `📜 Script` opens an accessible quick-review modal displaying all 4 scenes, camera cues, and character dialogue lines with a one-click transition to view the rendered clips.

---

### 2026-11-18 — Sample Episode Generation & Mock Run with Rendered Videos

Completed:
- **Sample Video Integration**:
  - Connected the 4 uploaded 9:16 vertical video renders (`media_1794985409925_750c3899.mp4`, `media_1794985409894_a50cd342.mp4`, `media_1794985409792_9516e926.mp4`, `media_1794985409813_6e670a44.mp4`) as sequential scene clips (Scene 1 to Scene 4) for full end-to-end testing.
  - Used FFmpeg via `app.media.merger.merge_scene_videos` to stitch the 4 scenes into a complete, seamless master 9:16 vertical video (`merged_60s.mp4`).
- **Studio Section & Episodes Section Availability**:
  - **Studio Queue (`/studio`)**: Configured active in-progress production episode `ep_1794920700` (`Episode_20261117_185656 - TikTok Trends: November 2026 | Updated Weekly`) with 5 trend pitches, full 4-scene script, 4 rendered scene clips, and master video ready for review at Gateway 3 (Stage 3 Video).
  - **Episodes Library (`/episodes`)**: Configured completed published episode `ep_1794988800` (`Episode 1 - TikTok Trends: November 2026 | The Crash Out`) displaying in the library table with full record view at `/episodes/ep_1794988800` featuring playable 9:16 master cut, scene breakdown cards, publisher copy, and seeding drafts.
- **Database Synchronization (PostgreSQL)**:
  - Synchronized records to `episodes`, `pitches`, and `scripts` tables using `app.db.save_episode_to_db`, `save_pitches_to_db`, and `save_scripts_to_db`.
  - Verified persistence and counts across Postgres and state manager JSON store.

---

### 2026-11-18 — New EC2 Instance Migration & Production Setup (`54.166.201.137`)

Completed:
- **New AWS EC2 Instance Provisioning**:
  - Successfully connected to the new EC2 instance (`i-01f129cddb4bbb15e`) in `us-east-1` with public IP `54.166.201.137` using the updated key `crashout.pem` (Ubuntu 26.04 LTS, default user `ubuntu`).
  - Configured AWS Security Group (`launch-wizard-1` / `sg-03d3d71d2b06a81b5`) to authorize inbound HTTP (port 80) and HTTPS (port 443) traffic.
- **Base Server Infrastructure**:
  - Installed system dependencies: `python3-pip`, `python3-venv`, `docker.io`, `nginx`, `git`, and `ffmpeg` (v8.0.1).
  - Cloned repository to `/var/www/Crash_Out` and deployed secure production `.env`.
  - Configured Python virtual environment at `/var/www/Crash_Out/venv` with `requirements.txt` and `openai`.
- **Database & pgvector Setup**:
  - Deployed Docker container `crashout-postgres` (`pgvector/pgvector:pg16`) with restart policy and persistent volume.
  - Initialized `crash_out` PostgreSQL database with `vector` extension.
- **Temporal Server & Web UI Live**:
  - Bound Temporal UI container to external port `8088` (`crashout-temporal-ui`).
  - Added ingress security rule in AWS Security Group `sg-03d3d71d2b06a81b5` opening TCP port 8088.
  - Verified public reachability at `http://54.166.201.137:8088/namespaces`.
- **Clean Web Server Setup**:
  - Completely purged all experimental SSL certs (`sslip.io` Certbot certificates and self-signed certificate files).
  - Configured Nginx to exclusively serve standard HTTP on port 80 proxying cleanly to the Uvicorn FastAPI backend.
  - Verified clean HTTP response on `http://54.166.201.137/login`.
- **Systemd & Nginx Configuration**:
  - Configured and enabled `crashout.service` systemd service running Uvicorn on port 8000.
  - All 4 initial PostgreSQL database migrations applied cleanly during application startup.
  - Set up Nginx reverse proxy on port 80 (`/etc/nginx/conf.d/crashout.conf`) pointing to `http://127.0.0.1:8000` with 500MB upload support.
  - Verified public HTTP access at `http://54.166.201.137/login` returning HTTP 200 with full Crash Out Studio UI.

---

### 2026-11-18 — Agent 2 Inline Title Pencil Edit & Clip Timeline Header Polish

Completed:
- **Deployment & Git Push Policy**: Added strict restriction in [AGENTS.md](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/AGENTS.md) that prohibits running `git push` or deploying/pulling changes to remote production servers without explicit user confirmation.
- **Agent 2 Inline Title Edit via Pencil Icon**:
  - Replaced the collapsible `<details>` and generic "Edit" button in [stage_2.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/partials/stages/stage_2.html) with an inline editable form accompanied by a pencil button (`✎`), mirroring the episode title edit pattern in the workspace header.
  - Clicking the pencil icon activates inline editing on the title/punchline with keyboard shortcuts (`Enter` to save, `Escape` to cancel) and blur autosave support via [ui.js](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/static/js/ui.js).
- **Clip Timeline & Duration in Scene Tabs**:
  - Enhanced [script_scene_block.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/partials/script_scene_block.html) scene navigation tabs to display both the clip label (`Clip 1`, `Clip 2`, `Clip 3`, `Clip 4`) and its explicit timeline range and duration (`00:00 - 00:08 · 8s`, `00:09 - 00:22 · 14s`, etc.).
  - Preserved full responsiveness and tab active state styling across desktop and mobile viewports.

---

### 2026-11-17 — Pgvector Deduplication, Temporal S3 Automation & UI Polish

Completed:
- **Agent 0 Delete Button Red Styling & Reliable Deletion Fix**:
  - Restyled delete button in Agent 0 Studio Queue table ([stage_0.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/partials/stages/stage_0.html)) with explicit red color palette: red stroke icon (`#dc2626`), red text, soft red border (`#fecaca`), and light red background (`#fef2f2`).
  - Replaced problematic modal wiring with direct, foolproof `hx-confirm="Delete “{{ display_title }}” from the queue? This cannot be undone."` and `hx-post="/ui/queue/{{ card.id }}/delete"` targeting `#workspace`.
  - Updated `ui_delete_catalog_video` in [ui.py](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/ui.py) to reliably handle deletion by catalog ID, custom catalog ID, or direct episode ID, cleaning up state and active episode pointers smoothly.
- **Login Password Visibility Toggle**: Added an eye icon toggle button to the password input in [auth_login.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/auth_login.html), allowing users to show and hide their password in plain text with SVG open/closed eye state icons. Pushed and deployed live to EC2.
- **Production Server Deployment & Live Launch**:
  - Merged `users/dev/vikas/update` into `master` and pushed to GitHub remote `origin/master`.
  - Pulled latest `master` codebase onto the AWS EC2 instance (`13.51.79.99` at `/var/www/Crash_Out`).
  - Deployed production environment `.env` with AWS S3 credentials and OpenAI API keys.
  - Installed system dependencies including static `ffmpeg 7.0.2` and Python packages (`requirements.txt`, `openai`).
  - Initialized Docker stack running PostgreSQL 16 (`pgvector`) with vector extensions and ran database migrations.
  - Configured and started persistent `crashout.service` systemd daemon on port 8000 and reverse-proxied with Nginx on port 80.
  - Confirmed live HTTP response on `http://13.51.79.99/login`.
- **Refined Sr. No. Typography**: Adjusted serial number values from heavy bold (700) to dark semi-bold (`font-weight: 600; color: var(--text);`) across [app.css](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/static/css/app.css) and templates ([stage_0.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/partials/stages/stage_0.html), [episodes.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/episodes.html), [credits.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/credits.html), [dashboard.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/dashboard.html)) for a cleaner, balanced look.
- **Universal Bold Sr. No. Styling**: Updated `.data-table tbody td.col-num` in [app.css](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/static/css/app.css#L2573-L2579) to enforce `font-weight: 700 !important; color: var(--text) !important;`, ensuring the serial numbers are prominently and consistently bolded across all tables without CSS inheritance overrides.
- **Agent 0 Studio Queue Table Structure**:
  - Replaced the listbox row styling with a clean, responsive data table structure matching the **Episode Management** page.
  - Included a top search bar (`Search video or ID...`) with live JavaScript row filtering.
  - Columns: `Sr. No.` (bold), `Title` (with subtitle and ID), `Duration`, `Status` badge, and `Actions` with primary **`Open →`** button and trash can delete action.
  - Row click selects the video; actions allow direct opening into production pipeline or deleting with modal confirmation.
- **Agent 1 Pitch Card Title Text Wrapping**:
  - Replaced single-line `<input type="text">` for the Pitch Title with an auto-wrapping multi-line `<textarea>` in [stage_1.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/partials/stages/stage_1.html).
  - Updated `.concept-inline-title` in [app.css](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/static/css/app.css) with `white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word;` ensuring long pitch headlines wrap properly across cards.
- **Agent 2 Script Stage Simplification**:
  - Removed manual "Save script version" button from Stage 2 header ([stage_2.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/partials/stages/stage_2.html)), leaving clean "Generate Video" CTA.
  - Converted script editing into a clean, unified single editable prompt box per scene with live character counting.
  - Integrated automatic autosave on typing (`hx-trigger="keyup changed delay:500ms"`) targeting a live `Autosaved` status badge without page interruption or manual saving required.
  - Updated scene tabs from numeric `1`, `2`, `3`, `4` to **`Clip 1`**, **`Clip 2`**, **`Clip 3`**, **`Clip 4`** in [script_scene_block.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/partials/script_scene_block.html) and enhanced tab styling in [app.css](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/static/css/app.css).
- **Mockup Ingestion Loading Feedback & In-App Alert**:
  - Configured the "Mockup" button in Stage 0 ([stage_0.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/partials/stages/stage_0.html)) to immediately gray out and disable on click (`disabled=true; opacity: 0.5; pointer-events: none;`) with text switching to `Searching...`.
  - Added global helper `window.showInAppToast()` in [ui.js](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/static/js/ui.js) that triggers an in-app alert toast: **"Searching for Trending Topics..."**.
- **Sequential Stage Progression & Locked Stepper**:
  - Enforced HITL progression in [workspace.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/partials/workspace.html#L3-L35): Future Agent stages remain disabled, grayed out (`opacity: 0.42; filter: grayscale(0.35); pointer-events: none;`), and show "Pending approval" until their prerequisite gateway is approved.
  - Server-side guard in `_resolve_viewing_stage()` ([ui.py](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/ui.py#L358-L372)) prevents bypassing locked stages via manual URL parameter entry until previous gateways are cleared.
- **Agent 3 Video Stage Credits Display**:
  - Injected scene-specific credit usage onto each individual scene video card header in Stage 3 (`⚡ <X.X> cr`), showing exact credits consumed for each scene render.
  - Added a dedicated **Total Credits** stat card (`⚡ <total> cr`) in the final merged episode stats grid next to Container, Audio, Aspect, and Duration.
  - Updated `_build_scene_cards()` in `app/ui.py` to calculate and provide per-scene credits from `cost_summary(ep)["by_scene"]`.
- **Dashboard Hero Heading Color**: Updated the "Production dashboard" header text color to pure white (`#ffffff !important`) in [dashboard.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/dashboard.html) and `.brand-hero-copy h1` in [app.css](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/static/css/app.css) ensuring optimal contrast against the banner background image and shadow.
- **Table Search Bar & Universal Sr. No. Typography**:
  - Added live filter search input with Search action button to both the **Credits Usage** table ([credits.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/credits.html)) and the **Episode Management** table ([episodes.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/episodes.html)).
  - Made the `Sr. No.` values bold and dark (`font-weight: 700; color: var(--text)`) across all tables.
  - Consistently styled headers (`Sr. No.`, `Title`, `Status`, etc.) across [credits.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/credits.html), [episodes.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/episodes.html), and [dashboard.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/dashboard.html) with dark text (`color: var(--text)`) and balanced semi-bold weight (`font-weight: 600`).
- **Credits Table Header Typography**: Styled table headers (`Sr. No.`, `Episode Title`, `Status`, `Scene Credits Breakdown`, `Total Credits`, `Actions`) with dark high-contrast text (`color: var(--text)`) and balanced semi-bold weight (`font-weight: 600`).
- **Credits Page KPI Cards & Table Formatting**:
  - Aligned Total Credits, Episodes with Generations, and Active Engine KPI cards in a single horizontal row (`grid-template-columns: repeat(3, minmax(0, 1fr))`).
  - Positioned the detailed episode breakdown table directly below the KPI bar.
  - Replaced `#` with `Sr. No.` in the table header.
  - Formatted all table header titles with bold text (`font-weight: 700`).
  - Made the serial number row values bold (`font-weight: 700`, using `loop.index`).
- **Cleaned Credits Page Header**: Removed the redundant "Total Used: 0.0 credits" chip from the top-right header of `credits.html`, keeping the KPI card layout clean.
- **Agent Roster Numbering Re-alignment**:
  - Re-aligned Agent stage designations across Agent Studio pipeline:
    - **Stage 0**: Agent 0 (Queue & Ingest)
    - **Stage 1**: Agent 1 (Pitches)
    - **Stage 2**: Agent 2 (Script)
    - **Stage 3**: Agent 3 (Video)
    - **Stage 4**: Agent 4 (Publish)
    - **Stage 5**: Agent 5 (Seeding)
  - Updated stepper labels, letter marks (`A0`, `A1`, `A2`, `A3`, `A4`, `A5`), and card headers across `app/ui.py` and `app/templates/partials/stages/stage_*.html`.
- **Dashboard Button Update**: Replaced "Open studio" buttons on the Production Dashboard ([dashboard.html](file:///c:/Users/vikas.DESKTOP-61LEE8B/Projects/Crash_Out/app/templates/dashboard.html)) with **Agent Studio** for consistent naming across the studio workflow.
- **Dedicated Credits Usage Page & Clickable Sidebar Link**:
  - Made the **Credits Used** widget in the left sidebar clickable, routing to `/credits` with active tab indicators and hover animations.
  - Built `app/templates/credits.html` with KPI counters (Total Credits, Episodes Rendered, Active Engine) and a detailed episode-by-episode breakdown table detailing scene-by-scene credits used and direct links to open each episode in Agent Studio.
  - Added `GET /credits` route in `app/ui.py` calculating exact scene credits across all state episodes via `cost_summary()`.
  - Updated all labels and captions from "Vidu Q4 Generation" to **Video Generations** in both the sidebar panel and credit usage breakdown.
- **Agent 0 Queue Attribution**: Updated Stage 0 labeling to **Agent 0 (Queue & Ingest)** across the stepper bar, marks (`A0`), and page title in `app/ui.py` and `app/templates/partials/stages/stage_0.html` to clearly reflect Agent 0's ownership of trend ingestion and queue population.
- **Queue Layout Cleanup**: Completely removed the "Revision notes" aside section from Stage 0 (Queue tab) in `app/templates/partials/workspace.html`, allowing the Studio Queue to occupy a clean, full-width single-column layout.
- **Trash Can Delete Icon & Universal Video Deletion**:
  - Replaced the plain `×` text with an SVG trash can icon across video queue items in Studio Queue.
  - Enabled deletion for all videos (including built-ins/catalog items) via `delete_manual_catalog_video()` so any video row can be removed with confirmation.
- **Agent Studio Pipeline & Credits Navigation**:
  - Explicitly labeled stages with their owning agents in Agent Studio stepper & cards: **Agent 0 (Pitch)**, **Agent 1 (Script)**, **Agent 2/3 (Video)**, **Agent 4 (Publish)**, **Agent 5 (Seeding)**.
  - Added dedicated **Credits Used** card in the left navigation sidebar displaying cumulative Vidu generation credits consumed across all episodes in real-time.
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
