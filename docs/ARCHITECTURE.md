# CRASH OUT — Architecture (POC)

## High-level flow

```mermaid
flowchart TD
  catalog[VideoCatalog_CustomCatalog]
  a0[Agent0_TrendIngest]
  g1[HITL_Gateway1_Concept]
  a1[Agent1_ScriptPackage]
  g2[HITL_Gateway2_Script]
  vidu[ViduQ4_reference2video]
  merge[FFmpeg_Merge]
  g3[HITL_Gateway3_Video]
  a4[Agent4_PublishDrafts]
  g4[HITL_Gateway4_SocialMerch]
  a5[Agent5_SeedingDrafts]
  g5[HITL_Gateway5_Seeding]

  catalog --> a0
  a0 --> g1
  g1 --> a1
  a1 --> g2
  g2 --> vidu
  vidu --> merge
  merge --> g3
  g3 --> a4
  a4 --> g4
  g4 --> a5
  a5 --> g5
```

## Key modules

| Path | Role |
|---|---|
| `run.py` | Entry — starts Uvicorn |
| `app/main.py` | FastAPI app, REST `/api/*`, Vidu render + merge |
| `app/ui.py` | HITL Hub routes (HTMX partials) |
| `app/state.py` | Episode state machine; index + per-episode JSON |
| `app/paths.py` | `outputs/ep_<id>_<Title>/`, public URL helpers |
| `app/config.py` | Vidu + Agent 0 credentials from `.env` |
| `app/personas.py` | Character bible + HOA script package |
| `app/catalog.py` | Built-in + custom catalog videos/concepts |
| `app/engines/vidu_engine.py` | Vidu Q4 client |
| `app/video_merger.py` | FFmpeg concat → `merged_60s.mp4` |
| `app/agents/agent_m_orchestrator.py` | Gateway approve + QA helpers + logs |
| `app/agents/agent_0_trend_ingest.py` | Gate 1 concepts (thin wrapper) |
| `app/trends/` | Live trend collect → filter → concept writer → cache |
| `app/agents/agent_1_scriptwriter.py` | Script package by `script_key` |
| `app/agents/agent_4_publisher.py` | Social/merch draft package |
| `app/agents/agent_5_seeder.py` | Community seeding drafts |
| `app/templates/` | Jinja HITL stages |
| `characters/` | Shared `*_9x16.png` refs (outside `outputs/`) |
| `outputs/` | Episode folders + `pipeline_index.json` + trend cache |

## Episode storage

- Folder: `outputs/ep_<episode_id>_<Sanitized Title>/`
- Files: `episode.json`, `.episode_id`, `scene_1..4.mp4`, `merged_60s.mp4`, optional merch mockup
- Index: `outputs/pipeline_index.json` (active episode + lightweight listing)
- Empty / no-progress episodes are pruned; mid-pipeline episodes with script or `gateway >= 2` are kept even without MP4s

## Agent 0 live ingest

```mermaid
flowchart LR
  reddit[Reddit_RSS_or_OAuth]
  gtrends[GoogleTrends_RSS]
  gdelt[GDELT]
  news[NewsAPI_optional]
  filter[ThemeFitFilter]
  writer[LLM_or_HeuristicWriter]
  cache[trend_concepts_cache.json]
  gate1[Three_Concept_Cards]

  reddit --> filter
  gtrends --> filter
  gdelt --> filter
  news --> filter
  filter --> writer
  writer --> cache
  writer --> gate1
  cache --> gate1
```

Fallback order: **live cards → quality cache → static HOA/Stanley concepts**.

## Env (see `.env.example`)

- **Required for video:** `VIDU_API_KEY`, Vidu model/base URL
- **Optional for Agent 0:** `REDDIT_*`, `NEWS_API_KEY`, `OPENAI_API_KEY` / `OPENAI_MODEL`
