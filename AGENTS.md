# AGENTS INSTRUCTIONS & ARCHITECTURE SPECIFICATION
**Project:** Crash Out — Multi-Agent Adult Satirical Animated Series Studio  
**Target Output:** 9:16 Vertical Video Micro-Dramas (South Park meets Arrested Development)

---

## 1. AGENT ROLES & HITL GATEWAY PIPELINE

The system operates across **5 Autonomous Agents** coordinated by an Orchestrator with **Human-in-the-Loop (HITL) Gateways**:

```
[Agent 0: Trend Ingest] 
      │
      ▼ (Gateway 1: Concept Approval)
[Agent 1: Scriptwriter] 
      │
      ▼ (Gateway 2: Script & Prompt Review)
[Agent 2 & 3: Audio & Vidu Q4 Video Animation] 
      │
      ▼ (Gateway 3: Master 9:16 Merged Video Review)
[Agent 4: Merch & Distribution Package] 
      │
      ▼ (Gateway 4: Merch Sign-Off)
[Agent 5: Guerrilla Seeder] 
      │
      ▼ (Gateway 5: Publishing Sign-Off -> Episodes Library)
```

### Agent Roster:
1. **Agent 0 (`app/agents/agent_0_trend_ingest.py`)**:
   - Ingests Layer B (Youth/Reddit/Meme/YouTube) first, then Layer A (Mainstream US news). Layer C removed.
   - Generates embeddings and runs cosine similarity deduplication via pgvector against previous days' pitches.
   - Outputs top 5 friction intersection pitches.
2. **Agent 1 (`app/agents/agent_1_scriptwriter.py`)**:
   - Transforms approved pitch into a 4-scene, 60-second episodic dialogue script (Gary, Linda, Chris, Chloe).
   - Crafts strict Vidu Q4 multi-character generation prompts per scene.
3. **Agent 2/3 (`app/studio/generation.py`, `app/engines/vidu_engine.py`)**:
   - Manages scene-by-scene 9:16 vertical video renders using Vidu reference2video / img2video.
   - Master FFmpeg stitcher (`app/media/merger.py`) stitches scenes into a seamless episode.
4. **Agent 4 (`app/agents/agent_4_publisher.py`)**:
   - Produces viral episode title, YouTube Shorts/TikTok/Instagram descriptions, hashtags, and hoodie merch punchline.
5. **Agent 5 (`app/agents/agent_5_seeder.py`)**:
   - Crafts guerrilla seeding drafts for target subreddits, TikTok comments, and Discord communities.

---

## 2. CODING CONVENTIONS & DESIGN PATTERNS

### A. Fallback-First Design
Every external service (OpenAI, Vidu, AWS S3, Temporal, Postgres) **must have an offline/graceful fallback**:
- **Postgres / pgvector**: If `DATABASE_URL` is empty or unreachable, fall back to SQLite / local JSON files.
- **OpenAI**: If `OPENAI_API_KEY` is not present, fall back to heuristic clustering and templated scripts.
- **AWS S3**: If credentials or bucket are missing, save assets to `outputs/` locally.
- **Temporal**: If Temporal cluster is not reachable, execute asynchronously in-process.

### B. Directory Structure & Asset Paths
- `app/paths.py`: **Single source of truth** for file system paths. Always use `OUTPUT_DIR`, `CHARACTERS_DIR`, `ASSETS_DIR`, etc. Never hardcode relative string paths.
- `assets/`: Root directory reserved for optional global intro/outro video bumpers (`intro.mp4`, `outro.mp4`).
- `app/static/assets/`: Public static assets (branding badges, character portrait references, t-shirt mockups).
- `outputs/`: Output folder for generated scene MP4s, merged master videos, and pitch archives.

### C. Database & Migrations
- SQLite (`data/app.db`) is used for user auth, session tokens, and encrypted credentials.
- PostgreSQL (`app_db`) is used for production vector operations (`pgvector`, `generated_pitches`, `temporal`).
- When writing schema changes, always update `docker/init-scripts/01-init.sql` and `app/trends/store.py`.

### D. UI & Styling Rules
- **CSS Hierarchy**: Headers (`h1`–`h6`) are bold (`font-weight: 700`). Table bodies, data cells, and list items must **not** be aggressively bolded (`font-weight: 400`).
- **Responsive Layout**: Sidebar must stay anchored to the left. On screens $\le 980\text{px}$, it collapses into a 3-line hamburger drawer button.
- **Jinja + HTMX**: Frontend updates should leverage HTMX partial swapping (`app/templates/partials/`) without full page reloads where appropriate.

---

## 3. SESSION LOGGING & DEPLOYMENT WORKFLOW

### A. Git Commit, Push & Deployment Restrictions
- **CRITICAL RESTRICTION — NO GIT COMMITS WITHOUT EXPLICIT PERMISSION**: Never run `git commit` unless the user EXPLICITLY requests or instructs to do so. All code changes, documentation updates, and modifications must remain uncommitted in the local working directory until the user specifically tells you to commit them.
- **CRITICAL RESTRICTION — NO REMOTE PUSH OR DEPLOY**: Never run `git push` to remote git repository or deploy/pull changes to the remote production server (e.g. AWS EC2) unless the user EXPLICITLY requests or instructs to do so. All development and testing must stay local until explicit user sign-off.

### B. Session Logging
Whenever code, architecture, or schemas are modified:
1. Update `docs/SESSION_STATE.md` with a timestamped entry detailing:
   - What was added / updated / removed.
   - The rationale and files affected.
2. Ensure `python run.py` passes import and syntax checks without regression.
