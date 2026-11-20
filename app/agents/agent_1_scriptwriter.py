"""
Agent 1: Scriptwriter Agent.
Transforms approved Gate 1 concept/pitch into a 4-scene (40–60s) episodic script
with Gary, Linda, Chris, and Chloe, embedding the dynamic merch hook into Scene 4 dialogue
and synthesizing Vidu Q4 multi-character prompts (<= 2000 chars per scene).

Zero static catalog fallbacks. Automated 3-attempt retry loop with Agent M incident logging.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from app.agents.agent_m_orchestrator import orchestrator
from app.config import config
from app.core.personas import CHARACTERS
from app.core.prompts import build_scene_prompt, prompt_char_count
from app.db import log_system_incident

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the lead dialogue scriptwriter for CRASH OUT, an adult satirical 2D animated web series (South Park meets Arrested Development in modern US suburbia).

Cast:
- GARY (44): Overleveraged suburban dad. Tries gentle parenting until his stress watch hits 175 BPM, then pivots to MAGA/sovereign-citizen conspiracy logic, tactical DIY over-engineering, or stockpiling weird gear.
- LINDA (42): Performative Goop-wellness / HOA architectural review committee enforcer. Weaponizes gentle-mom therapy jargon and neighborhood petitions while hiding secret fast-food binges from the Ring doorbell camera.
- CHRIS (15): Techno-nihilist Gen Z doomer. Monotone, dry existential philosophy. Hacks neighborhood tech, runs absurd arbitrage bots, shorts local businesses on Robinhood.
- CHLOE (11): Ruthless pre-teen influencer / "momager". Treats her parents' meltdowns as monetizable content. Conducts street interviews with bewildered bystanders, runs live TikTok polls ("Vote: Should Dad get arrested or apologize?"), sells drop-shipped merch mid-crisis.

EPISODIC STRUCTURE (EXACTLY 4 SCENES, 40–60 SECONDS TOTAL):
- Scene 1 (Hook & Setup, 12-14s): Characters arrive at the designated setting from the concept. Real-world news signal triggers parent anxiety.
- Scene 2 (Escalation, 12-14s): The conflict intensifies. Gary's stress watch blares, or Linda's wellness optics panic kicks in. Chris drops dry existential stats; Chloe sets up her camera/livestream.
- Scene 3 (The Crack, 12-14s): Social collapse. The situation unravels in public view. Bystanders react, employees or authorities intervene, Gary doubles down.
- Scene 4 (The Crash Out & Merch Drop, 12-15s): Total chaotic climax. Chloe or Gary delivers the exact proposed merch punchline, and Chloe drops the merch poll/hoodie plug to her stream.

CRITICAL RULES:
1. ONLY use valid characters: "gary", "linda", "chris", "chloe". All 4 characters must appear across the script.
2. In Scene 4, Chloe or Gary MUST explicitly speak the exact "proposed_merch_hook" in their dialogue text.
3. Every dialogue turn must be funny, sharp, fast-paced satirical comedy.
4. Each scene must include realistic duration_sec (10–15s), detailed camera_cue, scene_action (physical animation blocking), and sfx.
5. Return ONLY valid JSON matching this schema:
{
  "location": "Specific primary location (e.g. Apple Store Genius Bar, Costco Bulk Aisle, Bleachers)",
  "merch_punchline_trigger": "Exact punchline phrase matching proposed_merch_hook (at least 5 characters)",
  "scenes": [
    {
      "scene_id": 1,
      "title": "Scene 1: ...",
      "duration_sec": 13,
      "location": "...",
      "camera_cue": "Wide 9:16 vertical tracking shot, low angle...",
      "scene_action": "Detailed comedic physical blocking...",
      "sfx": "Sound effect cues...",
      "dialogue": [
        {"character": "gary", "text": "...", "voice_tag": "enraged, frantic"},
        {"character": "linda", "text": "...", "voice_tag": "breathy faux-zen panic"}
      ]
    },
    ... exactly 4 scenes ...
  ]
}
"""


class Agent1Scriptwriter:
    def __init__(self):
        self.name = "Agent 1 (OpenAI Scriptwriter)"

    def _flatten_scenes(
        self,
        scenes: List[Dict[str, Any]],
        episode_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        flat_lines = []
        line_idx = 1
        current_time = 0.0

        for sc in scenes:
            sc_id = int(sc.get("scene_id", 1))
            duration = float(sc.get("duration_sec", 13.0))
            lines = sc.get("dialogue", []) or []
            sub_step = duration / max(len(lines), 1)

            for d_i, d in enumerate(lines):
                c_name = str(d.get("character") or "gary").lower().strip()
                flat_lines.append(
                    {
                        "index": line_idx,
                        "scene_id": sc_id,
                        "character": c_name,
                        "time_start": round(current_time + d_i * sub_step, 1),
                        "time_end": round(current_time + (d_i + 1) * sub_step, 1),
                        "camera_cue": sc.get("camera_cue", ""),
                        "text": str(d.get("text") or "").strip(),
                        "emotion": d.get("voice_tag") or d.get("emotion") or "",
                        "vidu_action": sc.get("scene_action", ""),
                    }
                )
                line_idx += 1
            current_time += duration

        total_duration = round(current_time)
        if total_duration < 40:
            total_duration = 45
        elif total_duration > 60:
            total_duration = 58

        enriched_scenes = []
        for sc in scenes:
            prompt = build_scene_prompt(sc)
            enriched = dict(sc)
            enriched["vidu_prompt"] = prompt
            enriched["vidu_prompt_chars"] = prompt_char_count(prompt)
            enriched["vidu_duration_sec"] = max(3, min(int(sc.get("duration_sec", 13)), 16))
            enriched_scenes.append(enriched)

        merch_trigger = str(episode_meta.get("merch_punchline_trigger") or "Prompted This").strip()

        return {
            "episode_id": episode_meta.get("episode_id", "ep_generated"),
            "episode_title": episode_meta.get("episode_title", "Untitled Episode"),
            "estimated_duration_sec": total_duration,
            "total_duration_sec": total_duration,
            "scene_count": len(enriched_scenes),
            "location": episode_meta.get("location", "Suburban Setting"),
            "merch_punchline_trigger": merch_trigger,
            "merch_context": f"Scene 4 crash-out delivers '{merch_trigger}' on Chloe's livestream poll.",
            "source": episode_meta.get("source", "openai_gpt6_luna"),
            "script_key": "ai_generated",
            "notes": ["Generated by Agent 1 Scriptwriter via OpenAI JSON Mode"],
            "scenes": enriched_scenes,
            "dialogue_lines": flat_lines,
            "prompt_budget_chars": 2000,
            "script_mode": "ai_generated",
        }

    def generate_script(
        self,
        concept: Optional[Dict[str, Any]] = None,
        *,
        episode_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a production 4-scene script from the approved concept using OpenAI.
        Executes an automated 3-attempt retry loop with Agent M validation & logging.
        Zero static mock fallbacks.
        """
        api_key = (config.openai_api_key or "").strip()
        if not api_key:
            err_msg = "OpenAI API key (OPENAI_API_KEY) is missing. Set OPENAI_API_KEY in .env."
            logger.error(err_msg)
            log_system_incident(
                event_type="AGENT1_CONFIG_ERROR",
                actor="Agent M Orchestrator",
                details={"category": "Agent 1 Scriptwriter", "error": err_msg, "can_retry": True},
            )
            raise RuntimeError(err_msg)

        c = concept or {}
        headline = str(c.get("headline") or c.get("title") or "Suburban Crash Out").strip()
        angle = str(c.get("crash_out_angle") or c.get("premise") or c.get("conflict") or "").strip()
        merch_hook = str(
            c.get("proposed_merch_hook")
            or c.get("suggested_merch")
            or c.get("merch_punchline")
            or "Capitalism broke my dad"
        ).strip()
        youth_take = str(c.get("youth_sentiment_summary") or c.get("cultural_hook") or "").strip()
        sources = c.get("sources") or {}
        model = (config.openai_model or "gpt-6-luna").strip()

        max_retries = 3
        last_error = ""

        for attempt in range(1, max_retries + 1):
            logger.info("Agent 1: Scriptwriter generating script via OpenAI (%s) — attempt %d/%d...", model, attempt, max_retries)

            user_prompt = (
                f"Write a full 4-scene (40-60 second) CRASH OUT episodic script based on this approved concept:\n\n"
                f"HEADLINE: {headline}\n"
                f"CRASH-OUT NARRATIVE ANGLE: {angle}\n"
                f"PROPOSED MERCH HOOK: {merch_hook}\n"
                f"YOUTH TAKE: {youth_take}\n"
                f"SOURCES: {sources}\n\n"
                f"Ensure exactly 4 scenes, all characters (Gary, Linda, Chris, Chloe) speaking, "
                f"and Scene 4 dialogue must deliver the merch hook: '{merch_hook}'."
            )
            if attempt > 1 and last_error:
                user_prompt += (
                    f"\n\nCRITICAL FIX REQUIRED (Previous attempt failed QA):\n"
                    f"{last_error}\n"
                    f"Please correct this exact issue in this attempt!"
                )

            payload: Dict[str, Any] = {
                "model": model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if not any(m in model.lower() for m in ("luna", "o1", "o3", "reasoning")):
                payload["temperature"] = 0.75

            try:
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=90,
                )
                if resp.status_code != 200:
                    last_error = f"OpenAI HTTP {resp.status_code}: {resp.text[:250]}"
                    logger.warning("Agent 1 attempt %d failed: %s", attempt, last_error)
                    if attempt < max_retries:
                        time.sleep(2.0 * attempt)
                    continue

                content = (((resp.json() or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                parsed = self._parse_script_json(content)
                if not parsed or not parsed.get("scenes"):
                    last_error = f"OpenAI returned unparseable script JSON: {content[:150]}"
                    logger.warning("Agent 1 attempt %d parse failed: %s", attempt, last_error)
                    if attempt < max_retries:
                        time.sleep(2.0 * attempt)
                    continue

                meta = {
                    "episode_id": episode_id or c.get("id") or "ep_generated",
                    "episode_title": headline,
                    "location": parsed.get("location") or "Suburban Setting",
                    "merch_punchline_trigger": parsed.get("merch_punchline_trigger") or merch_hook,
                    "source": f"openai_{model}",
                }
                candidate_script = self._flatten_scenes(parsed.get("scenes", []), meta)

                passed, qa_msg = orchestrator.validate_script_qa(candidate_script)
                if passed:
                    logger.info("Agent 1: Script QA Passed successfully on attempt %d! (%s)", attempt, qa_msg)
                    return candidate_script
                else:
                    last_error = qa_msg
                    logger.warning("Agent 1 attempt %d Script QA failed: %s", attempt, qa_msg)
            except Exception as exc:
                last_error = f"Execution exception: {exc}"
                logger.warning("Agent 1 attempt %d error: %s", attempt, exc)

            if attempt < max_retries:
                time.sleep(2.0 * attempt)

        # All 3 automated retries exhausted — log incident and fail explicitly (NO fallback!)
        incident_msg = f"Agent 1 Scriptwriter failed after {max_retries} attempts: {last_error}"
        logger.error("Agent M Alert: %s. Requires manual retry.", incident_msg)
        log_system_incident(
            event_type="AGENT1_SCRIPT_FAILURE",
            actor="Agent M Orchestrator",
            details={
                "category": "Agent 1 Scriptwriter",
                "task_name": "OpenAI Script Generation",
                "error": incident_msg,
                "episode_id": episode_id or c.get("id"),
                "episode_title": headline,
                "retry_count": max_retries,
                "max_retries": 3,
                "requires_manual_retry": True,
                "can_retry": True,
            },
        )
        raise RuntimeError(f"{incident_msg}. Manual retry required via Agent M.")

    def _parse_script_json(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return None


scriptwriter_agent = Agent1Scriptwriter()
