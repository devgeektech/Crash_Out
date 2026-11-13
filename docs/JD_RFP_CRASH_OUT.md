# REQUEST FOR PROPOSAL (RFP)

**Autonomous Multi-Agent AI System for Animated Web Series Production & Distribution ("CRASH OUT")**

> **Project note:** This document is the **original client idea / RFP**. It is kept for reference only.  
> The live POC does **not** implement every agent, gateway, or integration listed here.  
> See [PRODUCT.md](PRODUCT.md) for current scope and [SESSION_STATE.md](SESSION_STATE.md) for what was actually built.

---

## Summary

REQUEST FOR PROPOSAL (RFP)  
Autonomous Multi-Agent AI System for Animated Web Series Production & Distribution ("CRASH OUT")

---

## 1. Executive Summary

We are seeking an experienced Full-Stack / AI Engineer (or agency) to architect and implement an end-to-end multi-agent pipeline for producing, publishing, and actively promoting an edgy animated satirical micro-series targeting American Gen Z / Teens titled **"CRASH OUT"**.

The system must be orchestrated by a Master Project Manager Agent (Orchestrator) overseeing quality, latency, task delegation, and execution integrity. Crucially, the entire system architecture must be strictly designed around **Human-in-the-Loop (HITL) Gateways** at every stage: no downstream agent may trigger execution until the product owner explicitly reviews and approves the deliverable of the preceding stage via an administrative interface.

---

## 2. Multi-Agent Pipeline Architecture & Workflow

*(Attached in original RFP materials — see agent specs below.)*

---

## 3. Detailed Agent Specifications

### Agent M: Master Orchestrator & QA Agent (System Supervisor)

**Role & Responsibility:** Acts as the executive technical director of the system.

**Core Functions:**

- **Task Scheduling & SLA Monitoring:** Tracks deadlines, manages API rate limits, orchestrates queuing across sub-agents, and logs processing times.
- **Automated QA & Validation:** Validates intermediate outputs against strict schema and aesthetic rules before sending them to the user (e.g., verifying that script JSON has all mandatory fields, confirming audio duration matches target video limits, detecting visual glitches or black frames).
- **Self-Healing & Fallbacks:** Automatically triggers retries or fallback model endpoints if a third-party API times out or produces corrupted files.
- **State & Milestone Tracking:** Maintains a persistent state machine of the entire episode pipeline, dispatching human approval notifications and waiting for callbacks.

### Agent 0: US News & Viral Trend Ingestion

**Objective:** Daily scanning and aggregation of top trending, controversial, and cultural topics in the US.

**Integrations:** News APIs, RSS feeds of major US outlets, Reddit trend scrapers, Google Trends, and X (Twitter) APIs.

**Outputs:** Delivers 3 daily satirical episode concepts framed through the lens of a dysfunctional suburban family.

**HITL Gateway 1:** Sends topic cards to the admin dashboard/Telegram bot with clickable options (Approve Idea 1, Approve Idea 2, Regenerate). Downstream scripting is blocked until approved.

### Agent 1: Satirical Scriptwriter & Merch Triggers

**Objective:** Writes a 30–60 second dialogue script matching established character bibles (Gary, Linda, Chris, Chloe) and current American teen/Gen Z slang.

**Output:** JSON schema containing dialogue lines, timestamps, camera cues, and an auto-tagged Merch Punchline Trigger (e.g., "Capitalism broke my dad" or "It's not gaslighting if I'm historically correct").

**HITL Gateway 2:** Delivers formatted script text and merch line to the user for review, editing, or 1-click sign-off.

### Agent 2: Multi-Character Voice Synthesis (TTS)

**Objective:** Synthesizes voice tracks from the approved script.

**Integrations:** ElevenLabs API (or equivalent voice engine) using dedicated voice IDs for each family member.

**Outputs:** Isolated character stems and an assembled dialogue mix.

**HITL Gateway 3:** Pushes preview audio to the user. User can trigger regeneration of specific lines or approve audio for visual sync.

### Agent 3: 2D Animation, Lip-Sync & Auto-Captioning

**Objective:** Animates character assets, coordinates lip-sync with audio, renders layered composite scenes, and adds dynamic kinetic subtitles.

**Integrations:** Lip-sync engines (D-ID API, Hedra API, LivePortrait, Wav2Lip, or Fal.ai endpoints) composited via FFmpeg / MoviePy.

**Outputs:** High-definition 9:16 vertical MP4 video with official outro bug and branding.

**HITL Gateway 4:** Full final video preview presented to the user for final sign-off before any public release.

### Agent 4: Multi-Channel Publishing & Merch Deployment

**Social Deployment:** Auto-formats and posts approved video to YouTube Shorts, TikTok, and Instagram Reels with algorithm-optimized metadata.

**E-Commerce Integration:** Passes approved merch punchline to typography templates, auto-creates product listings in Print-on-Demand storefronts (Shopify / Printify API), and embeds trackable store links in video descriptions.

**HITL Gateway 5:** Presents final post metadata, tags, and product mockup for one-click publishing authorization.

### Agent 5: Active Community Seeding & Guerrilla Promotion Agent

**Objective:** Drives organic engagement across external platforms (Reddit subreddits, Discord communities, X threads, parenting groups).

**Core Responsibilities:** Detects active public discussions related to the episode’s topic, prepares contextual, meme-literate responses/clips, and applies safety/anti-spam limits.

**HITL Gateway 6:** Submits proposed external comment drafts, target thread URLs, and attached media to the user before posting, ensuring complete brand and account safety.

---

## 4. Technical Stack & Architecture Preferences

- **Orchestration Framework:** Python (LangGraph / CrewAI / Temporal) to handle persistent multi-stage state machines with conditional waiting states.
- **Unified Admin Interface (HITL Hub):** A dedicated Telegram Bot interface (with inline action buttons) AND/OR a clean web dashboard (Next.js / Streamlit) showing the real-time status of each agent, previews (text, audio, video), and single-click approval controls.
- **Queuing & Storage:** Cloud object storage (AWS S3 / Supabase) with message queues (Redis / Celery) for render workloads.

---

## 5. Requirements for Proposal Submission (For Bidders)

Please address the following points directly in your response:

1. **System & Orchestration Architecture:** Explain how you will architect the Master Orchestrator Agent to enforce workflow dependencies, handle error recovery, and pause pipeline states for human approval.
2. **HITL Interface Design:** Specify your proposed interface for human review and sign-off (e.g., Telegram bot callbacks, customized web dashboard).
3. **Timeline & Milestone Plan:** Provide a breakdown of phases from proof of concept (POC) to production deployment.
4. **Itemized Third-Party API & Operational Costs (Mandatory):**
   - List all required third-party APIs (LLM inference, ElevenLabs, video/lip-sync APIs, news scrapers, hosting, proxies).
   - Provide an estimated monthly running cost based on a production cadence of 3 to 5 video episodes per week.
5. **Portfolio & Relevant Experience:** Share relevant projects involving multi-agent workflows, media automation, voice synthesis, or headless browser automation.
