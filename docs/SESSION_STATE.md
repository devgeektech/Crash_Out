# CRASH OUT — Session State

Living log of meaningful project changes. Keep this updated as work lands.  
Do **not** treat the JD as a delivery checklist — see [PRODUCT.md](PRODUCT.md).

**Refs:** [JD_RFP_CRASH_OUT.md](JD_RFP_CRASH_OUT.md) (idea) · [ARCHITECTURE.md](ARCHITECTURE.md) · `README.md` · `AGENTS.md`

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
