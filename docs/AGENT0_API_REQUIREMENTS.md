# Agent 0 — Paid APIs & What You Need

**Short answer:** You do **not** need any paid API for Agent 0 to run. It already falls back to free/public sources + heuristic scoring. Paid keys only improve quality.

---

## Works with $0 (already built-in)

| Piece | How |
|---|---|
| Layer A | Google Trends RSS, public news RSS, DuckDuckGo web search |
| Layer B | Reddit, YouTube trending, Know Your Meme / youth slang RSS |
| Clustering | Jaccard text similarity (no embeddings); OpenAI embeddings when keyed |
| Scoring | Heuristic friction scorer (no LLM) |
| Storage | Files under `outputs/agent0/` |
| Schedule / Telegram | Optional; off by default |

So: **no paid API required.**

---

## Paid / credit-based (optional, better quality)

| Item | Need? | Cost shape | Why |
|---|---|---|---|
| **OpenAI** (`OPENAI_API_KEY`) | Strongly recommended | Usage-based | Real friction scoring + better clustering embeddings |
| **NewsAPI** or **GNews** | Nice to have | Free tier, then paid | Real multi-outlet mainstream consensus |
| **SerpApi** | Optional | Paid | Google Trends fallback if RSS is thin |
| **YouTube Data API** | Optional | Free quota, then paid | US trending video cross-check |
| **Postgres + pgvector** (`DATABASE_URL`) | Optional | Hosting cost | Durable memory / 30-day dedupe (files work without it) |

---

## Free accounts (not “paid,” but you may need to sign up)

| Item | Need? | Notes |
|---|---|---|
| **Reddit app** (client id/secret) | Optional | Public JSON works; PRAW is more stable |
| **Telegram bot** + chat id | Optional | Only if you want daily pitch push |
| **APScheduler flag** | Optional | Set `AGENT0_SCHEDULE_ENABLED=true` for 06:00 ET runs |

---

## Minimum recommended setup (best bang for money)

1. **`OPENAI_API_KEY`** — biggest quality jump  
2. **`NEWSAPI_API_KEY` or `GNEWS_API_KEY`** — better Layer A  
3. Everything else can stay empty for now  

---

## Not needed for Agent 0

- Vidu credits  
- ElevenLabs  
- Temporal Cloud  
- TikTok Creative Center  

---

## Env keys reference

See [`.env.example`](../.env.example) for the full list:

- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBED_MODEL`
- `NEWSAPI_API_KEY`, `GNEWS_API_KEY`, `SERPAPI_API_KEY`
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`
- `YOUTUBE_API_KEY`
- `DATABASE_URL`
- `AGENT0_SCHEDULE_ENABLED`, `AGENT0_SCHEDULE_HOUR`, `AGENT0_SCHEDULE_MINUTE`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

---

**Bottom line:** Agent 0 runs unpaid today. Add OpenAI (+ one news API) when you want client-spec quality pitches.
