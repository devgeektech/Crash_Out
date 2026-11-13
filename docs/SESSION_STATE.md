# CRASH OUT — Session State

Living log of meaningful project changes. Keep this updated as work lands.  
Do **not** treat the JD as a delivery checklist — see [PRODUCT.md](PRODUCT.md).

**Refs:** [JD_RFP_CRASH_OUT.md](JD_RFP_CRASH_OUT.md) (idea) · [ARCHITECTURE.md](ARCHITECTURE.md) · `README.md`

---

### 2026-11-13 — Project docs + Agent 0 live trend ingestion

Completed:
- Saved original RFP/JD to `docs/JD_RFP_CRASH_OUT.md` (reference only).
- Added `docs/PRODUCT.md` (POC scope vs JD), `docs/ARCHITECTURE.md`, and this session file.
- Clarified product rule: continue current Vidu/HITL POC path; JD is idea guidance, not full build scope.
- **Agent 0 live topics:** `app/trends/` pipeline — Reddit RSS (multi-sub) / optional OAuth, Google Trends RSS, GDELT, optional NewsAPI → theme fit filter → OpenAI or heuristic concept writer → `outputs/trend_concepts_cache.json` → static fallback.
- Env placeholders: `REDDIT_*`, `NEWS_API_KEY`, `OPENAI_API_KEY`, `OPENAI_MODEL` in `.env` / `.env.example`.
- Gate 1 refresh logs concept titles; filter rejects violence/politics noise and requires strong suburban/culture tokens in titles.

Pending:
- Optional: wire Telegram HITL (JD) — not started.
- Optional: real LLM scriptwriter (Agent 1) — still package/catalog based.
- Optional: live social post / Printify — still drafts only.

Issues:
- Reddit/GDELT can 429 under repeated local testing; cache/static fallback keeps Gate 1 usable.

Next:
- Continue POC polish as needed; when adding features, update this file.

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
