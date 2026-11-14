# CRASH OUT — Product Overview (POC)

## Intent

Build a **practical HITL production studio** for the satirical animated micro-series **CRASH OUT** (Gary, Linda, Chris, Chloe), aimed at American Gen Z / teens.

The original client **RFP / JD** ([JD_RFP_CRASH_OUT.md](JD_RFP_CRASH_OUT.md)) is the **idea reference** — full multi-agent production + distribution vision.  
This repo implements a **POC path**: keep the HITL spirit and agent names, ship working video generation first, and expand toward the JD only where it fits the current build.

**We are not committing to implement every JD agent/integration.** Development continues in the direction we are already going, using the JD as thematic and architectural guidance.

---

## Characters & tone (from Personas bible)

- **Gary (44)** — MAGA “gentle parent” suburban dad; therapy jargon → rally rant; stress watch.
- **Linda (42)** — Goop / HOA optics hypocrite; Stanley tumbler; secret junk food.
- **Chris (15)** — Techno-nihilist doomer; late-stage capitalism monologues.
- **Chloe (11)** — Pre-teen momager; livestreams and monetizes family meltdowns.

Comic engine: suburban status anxiety × Gen Z digital extraction × performative wellness. No real healing — every beat ends in a crash-out.

---

## What the POC actually builds

| JD idea | POC reality |
|---|---|
| Agent M orchestrator + QA | FastAPI orchestrator + logs + gateway validation |
| Agent 0 live US trends → 3 concepts | Web search (`ddgs`) for hot topics → filter → 3 concept cards (+ optional OpenAI writer; cache/static fallback) |
| HITL Gate 1 concept approve | Web HITL Hub (Jinja + HTMX) |
| Agent 1 LLM scriptwriter | Script packages / catalog prompts (HOA + Q4 prompt cut + manual catalog); editable prompts in UI |
| Agent 2 ElevenLabs TTS | **Skipped** — dialogue + voice tags go into Vidu prompts; **audio is generated inside Vidu** (`audio: true`) |
| Agent 3 lip-sync / D-ID / Hedra | **Skipped** — Vidu Q4 produces picture + spoken audio together; no separate lip-sync engine |
| Studio episode mgmt / char library / queue | `/episodes`, `/characters`, mock-safe queue + clip history |
| Script versions / dialogue edit / templates | Script stage tools: versions restore, per-line edit, prompt templates |
| Clip history restore / export / cost | Restore archived clips; ZIP + 16:9 export; cost ledger panel |
| Background jobs / notifications | Daemon worker processes waiting queue jobs |
| Voice / timing for Vidu | Character audio tags + script dialogue timing feed Vidu prompts (not a TTS API) |
| QA + continuity | Human checklists; FFmpeg last-frame extract for next-clip continuity |
| Agent 4 social + Shopify/Printify | Draft metadata + merch mockup in UI (no live posting/store yet) |
| Agent 5 community seeding | Draft seeding package in UI (no live posting) |
| Telegram bot HITL | **Not built** — web dashboard only |
| LangGraph / Temporal / S3 / Celery | **Not built** — local FastAPI + `outputs/` episode folders |

---

## Current HITL stages (POC)

```
Video queue / catalog
        ↓
[Agent 0] Concepts  →  HITL Gateway 1
        ↓
[Agent 1] Script + merch  →  HITL Gateway 2
        ↓
Vidu Q4 × 4 scenes → FFmpeg merge  →  HITL Gateway 3 (video preview)
        ↓
[Agent 4] Social + merch package  →  HITL Gateway 4
        ↓
[Agent 5] Seeding drafts  →  HITL Gateway 5
```

Episode media lives under `outputs/ep_<id>_<Title>/` with per-episode `episode.json`. Shared character refs live in `characters/` (`*_9x16.png`).

---

## Stack (as built)

- **App:** Python FastAPI + Uvicorn
- **HITL UI:** Jinja2 + HTMX (`app/ui.py`, `app/templates/`)
- **Video:** Vidu Q4 Preview API (`reference2video` / `img2video`), native audio
- **Merge:** FFmpeg via `imageio-ffmpeg`
- **State:** `outputs/pipeline_index.json` + per-folder `episode.json`
- **Trends:** `app/trends/` (Agent 0)

---

## Docs map

| File | Purpose |
|---|---|
| [JD_RFP_CRASH_OUT.md](JD_RFP_CRASH_OUT.md) | Original RFP / JD (idea reference) |
| [PRODUCT.md](PRODUCT.md) | This file — POC scope vs JD |
| [SESSION_STATE.md](SESSION_STATE.md) | Living session log of completed work |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Code layout & data flow |
| `../README.md` | Quick start |

---

## Guiding rule for future work

1. Prefer finishing a working POC path over JD completeness.  
2. When adding features, map them to a JD agent/gateway if useful — but **do not** add separate TTS or lip-sync engines; audio stays Vidu-native.  
3. Update [SESSION_STATE.md](SESSION_STATE.md) whenever meaningful changes land.
