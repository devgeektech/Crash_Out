# "CRASH OUT" — Autonomous Multi-Agent AI Web Series Production Studio (POC)

End-to-end multi-agent production pipeline for the animated satirical micro-series **"CRASH OUT"**, targeting American Gen Z / teens.

Supervised by **Agent M** with strict **Human-in-the-Loop (HITL)** gateways. Video generation is **Vidu Q4 Preview (Video)** via the official platform API.

### Docs

| Doc | What it is |
|---|---|
| [docs/JD_RFP_CRASH_OUT.md](docs/JD_RFP_CRASH_OUT.md) | Original RFP / job description — **idea reference only** |
| [docs/PRODUCT.md](docs/PRODUCT.md) | What this POC actually builds vs the JD |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Code layout, storage, Agent 0 ingest |
| [docs/SESSION_STATE.md](docs/SESSION_STATE.md) | Living session log — update as we change things |

We are **not** implementing the full JD. Development continues on the current Vidu + HITL web hub path, using the JD only for direction.

---

## Video Engine: Vidu Q4 Preview

Uses [Vidu Q4 Preview API](https://platform.vidu.com/docs/api-reference/video-models/vidu-q4-preview/reference-to-video):

| Capability | Endpoint | Model |
|---|---|---|
| Reference → Video (preferred, 9:16) | `POST /ent/v2/reference2video` | `viduq4-preview` |
| Image → Video (single start frame) | `POST /ent/v2/img2video` | `viduq4-preview` |
| Poll result | `GET /ent/v2/tasks/{id}/creations` | — |

**Important:** Q4 Preview has **no text-to-video**. Every scene needs at least one character reference image from `characters/`.

Auth header format:

```http
Authorization: Token {VIDU_API_KEY}
```

Base URL: `https://api.vidu.com`

Each episode targets **~40–60s**. Script generation is not wired yet — Agent 1 always ships the attached fixed PDF script (**The HOA Violation**, ~55s, 4 timed beats: 8/14/16/16s). Vidu Q4 clips are 3–16s with native audio. Prompts are capped at **2000 characters**. Scenes are merged with FFmpeg into one vertical `9:16` master.

---

## Multi-Agent Architecture & 5 HITL Gateways

```
[Agent 0: US Trend Ingestion]
         ↓
  [HITL Gateway 1] ---> approve 1 of 3 concepts
         ↓
[Agent 1: Fixed Script Package (PDF → 4 scenes)]
         ↓
  [HITL Gateway 2] ---> approve script → Vidu Q4 renders 4 scenes → FFmpeg merge
         ↓
  [HITL Gateway 3] ---> preview 9:16 video with native audio
         ↓
[Agent 4: Publishing & Merch Mockups]
         ↓
  [HITL Gateway 4] ---> authorize social / merch package
         ↓
[Agent 5: Community Seeding Drafts]
         ↓
  [HITL Gateway 5] ---> review seeding drafts
         ↓
    [PRODUCTION COMPLETE]
```

---

## Setup

1. Copy env template and add your key from [platform.vidu.com](https://platform.vidu.com):

```bash
copy .env.example .env
```

Edit `.env`:

```env
VIDU_API_KEY=your_token_here
VIDU_BASE_URL=https://api.vidu.com
VIDU_MODEL=viduq4-preview
VIDU_REFERENCE_MODEL=viduq4-preview
VIDU_RESOLUTION=720p
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Launch HITL Hub:

```bash
python run.py
```

Open **http://127.0.0.1:8000**

The HITL UI is **Jinja2 + HTMX** (server-rendered partials, light theme). JSON `/api/*` routes remain for scripts and tooling.

---

## Notes

- Scenes use **reference2video** with Gary / Linda / Chris / Chloe PNGs for character consistency and `9:16`.
- Native audio (`audio: true`) is always requested.
- Kling, Hedra, simulator, and Q3 text2video paths are removed.
