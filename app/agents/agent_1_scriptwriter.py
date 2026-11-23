"""
Agent 1: Scriptwriter Agent.
Transforms approved Gate 1 concept/pitch into a 4-scene (56–58s) episodic script
with active character roster, embedding the dynamic merch hook naturally across scenes
and synthesizing Vidu Q4 multi-character prompts (<= 2000 chars per scene).

Zero static catalog fallbacks. Automated 3-attempt retry loop with Agent M incident logging.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.agents.agent_m_orchestrator import orchestrator
from app.config import config
from app.core.personas import CHARACTERS
from app.core.prompts import build_scene_prompt, prompt_char_count
from app.db import log_system_incident

logger = logging.getLogger(__name__)


def build_scriptwriter_system_prompt(cast_characters: Optional[List[Dict[str, Any]]] = None) -> Tuple[str, List[str]]:
    """
    Build a dynamic system prompt synchronized with the Character Library.
    Pulls character details (archetype, mannerisms, psychological profile, voice)
    so newly added or edited characters in the UI are immediately respected.
    """
    from app.studio.characters import list_characters

    try:
        chars = cast_characters or list_characters()
    except Exception:
        chars = []

    if not chars:
        from app.core.personas import CHARACTERS
        chars = list(CHARACTERS.values())

    roster_lines = []
    valid_ids = []
    display_names = []

    for c in chars:
        cid = str(c.get("id") or "").lower().strip()
        cname = str(c.get("name") or cid.capitalize()).strip()
        age_val = c.get("age")
        age_str = f"({age_val})" if age_val else ""
        role = str(c.get("role") or "").strip()
        archetype = str(c.get("archetype") or "").strip()
        desc = str(c.get("description") or "").strip()
        mannerisms = str(c.get("personality") or "").strip()
        voice_tone = str((c.get("voice") or {}).get("tone") or "").strip()

        detail_parts = []
        if archetype:
            detail_parts.append(archetype)
        if role:
            detail_parts.append(f"Role: {role}")
        if desc:
            detail_parts.append(desc)
        if mannerisms:
            detail_parts.append(f"Mannerisms: {mannerisms}")
        if voice_tone:
            detail_parts.append(f"Voice: {voice_tone}")

        summary = ". ".join(detail_parts) if detail_parts else "Suburban character in CRASH OUT universe."
        roster_lines.append(f"- {cname.upper()} {age_str} [character_id: \"{cid}\"]: {summary}")
        valid_ids.append(cid)
        display_names.append(cname)

    roster_text = "\n".join(roster_lines)
    valid_ids_formatted = ", ".join(f'"{cid}"' for cid in valid_ids)
    names_formatted = ", ".join(display_names)

    prompt = f"""You are the lead dialogue scriptwriter for CRASH OUT, an adult satirical 2D animated web series (South Park meets Arrested Development in modern US suburbia).

CAST & CHARACTER ROSTER (Directly synchronized from Studio Character Library):
{roster_text}

EPISODIC STRUCTURE (EXACTLY 4 SCENES, 56–58 SECONDS TOTAL RUNTIME):
- Scene 1 (Hook & Setup): EXACTLY 15 seconds. Characters arrive at the designated setting from the concept. Real-world news signal triggers anxiety or absurdity.
- Scene 2 (Escalation): EXACTLY 15 seconds. The conflict intensifies. Character psychological flaws flare up; secondary characters drop dry commentary or reactions.
- Scene 3 (The Crack): EXACTLY 15 seconds. Social collapse. The situation unravels in public view. Bystanders react, employees or authorities intervene, chaos peaks.
- Scene 4 (The Crash Out & Climax): 11–13 seconds (total episode runtime MUST be between 56 and 58 seconds). Climax and comedic fallout.

BALANCED DIALOGUE DENSITY & PACING (NATURAL SATIRICAL SWEET SPOT):
1. PACING & WORD COUNT (MEDIUM CADENCE):
   - Deliver balanced, punchy dialogue with comedic timing (approx 20–30 spoken words total per 15s scene).
   - Avoid extremes: DO NOT write sparse 1–2 line scenes (which leaves awkward dead air), but DO NOT cram 5–6 breathless, rushed lines either.
   - Each 15-second scene (Scenes 1, 2, and 3) MUST have 3 to 4 well-paced dialogue turns (roughly 6–10 words per line, natural conversational speed ~2.0–2.4 words/sec).
   - Scene 4 (11–13s) MUST contain 2 to 4 dialogue turns (approx 15–25 spoken words total).
   - Characters banter, bounce off each other, and react with sharp suburban wit while leaving room for physical comedic action and visual cuts.
2. CINEMATIC DIRECTING CUES & 2000-CHAR PROMPT DENSITY:
   - Target 1500 to 1850 characters per scene (within Vidu Q4's 2000-character budget).
   - Every single dialogue line MUST have its own camera movement, physical action, and sound cue:
     - `camera_cue`: Specific cinematic camera cut or shot framing this speaker (e.g., 'Cut to medium close-up on Chloe holding phone to selfie view', 'Rapid vertical whip-pan right to Gary beside folding chairs', 'Low angle tilt down to Chris slumped against wall typing', 'Dynamic push-in on Gary\'s manic expression').
     - `action`: Specific physical body action, hand movement, or facial reaction of this speaker while talking (e.g., 'snaps open his laminated map like a presentation board', 'smiles serenely while clutching herbal tea with both hands', 'looks at floor scrolling on phone without expression').
     - `voice_tag`: Distinct vocal delivery and emotional tone (e.g., 'sugary influencer urgency', 'soft therapist voice growing nasal', 'breathy faux-zen', 'flat monotone teen drawl').
     - `sfx`: Specific sound event occurring during this exact line (e.g., 'Laminated map snaps open', 'Phone alert chime', 'Rapid mechanical click-clack') or empty string if ambient sound continues.
   - Scene-level:
     - `scene_action`: 3–4 detailed sentences detailing the suburban environment, background props, lighting, atmosphere, and character physical positioning across the room.
     - `camera_cue`: Master 9:16 vertical camera setup for the clip.
     - `sfx`: Layered ambient sound effects for the scene.
3. DYNAMIC CAST ROSTER:
   - ONLY use valid character IDs from the active registered roster: {valid_ids_formatted}. The active cast ({names_formatted}) should be engaged across the episode. Note: Characters can be added, updated, or removed from the Character Library; always adhere strictly to the registered roster provided above.
4. SCENE DURATIONS:
   - Must follow: Scene 1: 15s, Scene 2: 15s, Scene 3: 15s, Scene 4: 11–13s, so total episode runtime is strictly between 56 and 58 seconds total.
5. SATIRICAL MERCH HOOK (ANY SCENE):
   - A speaking character MUST naturally deliver the exact "proposed_merch_hook" in their dialogue text in ANY scene (Scene 1, Scene 2, Scene 3, or Scene 4) where it best lands with maximum comedic punch. It does NOT have to be restricted to Scene 4.
6. Return ONLY valid JSON matching this schema:
{{
  "location": "Specific primary location (e.g. Apple Store Genius Bar, Costco Bulk Aisle, Bleachers)",
  "merch_punchline_trigger": "Exact punchline phrase matching proposed_merch_hook (spoken in any scene, at least 5 characters)",
  "scenes": [
    {{
      "scene_id": 1,
      "title": "Scene 1: ...",
      "duration_sec": 15,
      "location": "...",
      "camera_cue": "Wide 9:16 vertical tracking shot, low angle...",
      "scene_action": "Detailed comedic physical staging and movement of characters across the set...",
      "sfx": "Master sound effect and environmental audio cues...",
      "dialogue": [
        {{
          "character": "<valid_character_id>",
          "text": "snappy spoken dialogue line (6-10 words)",
          "voice_tag": "emotional vocal delivery",
          "action": "specific physical body action or facial reaction while speaking",
          "camera_cue": "specific camera cut or framing for this turn",
          "sfx": "sound trigger occurring on this line or empty string"
        }}
      ]
    }},
    {{
      "scene_id": 2,
      "title": "Scene 2: ...",
      "duration_sec": 15,
      "location": "...",
      "camera_cue": "...",
      "scene_action": "...",
      "sfx": "...",
      "dialogue": [...]
    }},
    {{
      "scene_id": 3,
      "title": "Scene 3: ...",
      "duration_sec": 15,
      "location": "...",
      "camera_cue": "...",
      "scene_action": "...",
      "sfx": "...",
      "dialogue": [...]
    }},
    {{
      "scene_id": 4,
      "title": "Scene 4: ...",
      "duration_sec": 12,
      "location": "...",
      "camera_cue": "...",
      "scene_action": "...",
      "sfx": "...",
      "dialogue": [...]
    }}
  ]
}}
"""
    return prompt, valid_ids


class Agent1Scriptwriter:
    def __init__(self):
        self.name = "Agent 1 (OpenAI Scriptwriter)"

    def _flatten_scenes(
        self,
        scenes: List[Dict[str, Any]],
        episode_meta: Dict[str, Any],
        valid_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        flat_lines = []
        line_idx = 1
        current_time = 0.0
        default_char = valid_ids[0] if (valid_ids and len(valid_ids) > 0) else "gary"

        # Enforce exact production timing: Scene 1 = 15s, Scene 2 = 15s, Scene 3 = 15s, Scene 4 = remainder (11-13s, total 56-58s)
        for i, sc in enumerate(scenes):
            sc_id = int(sc.get("scene_id", i + 1))
            if sc_id in (1, 2, 3):
                sc["duration_sec"] = 15
            elif sc_id == 4:
                raw_s4 = int(sc.get("duration_sec", 12))
                sc["duration_sec"] = max(11, min(13, raw_s4 if raw_s4 in (11, 12, 13) else 12))

        for sc in scenes:
            sc_id = int(sc.get("scene_id", 1))
            duration = float(sc.get("duration_sec", 15.0 if sc_id in (1, 2, 3) else 12.0))
            lines = sc.get("dialogue", []) or []
            sub_step = duration / max(len(lines), 1)

            for d_i, d in enumerate(lines):
                c_name = str(d.get("character") or default_char).lower().strip()
                action_text = d.get("action") or ""
                vtag = d.get("voice_tag") or d.get("emotion") or ""
                flat_lines.append(
                    {
                        "index": line_idx,
                        "line_id": f"line_{line_idx}",
                        "scene_id": sc_id,
                        "character": c_name,
                        "time_start": round(current_time + d_i * sub_step, 1),
                        "time_end": round(current_time + (d_i + 1) * sub_step, 1),
                        "camera_cue": d.get("camera_cue") or "",
                        "text": str(d.get("text") or "").strip(),
                        "emotion": vtag,
                        "voice_tag": vtag,
                        "action": action_text,
                        "vidu_action": action_text,
                        "sfx": d.get("sfx") or "",
                    }
                )
                line_idx += 1
            current_time += duration

        total_duration = round(current_time)
        if total_duration < 56:
            if len(scenes) >= 4:
                scenes[3]["duration_sec"] = 11
            total_duration = 56
        elif total_duration > 58:
            if len(scenes) >= 4:
                scenes[3]["duration_sec"] = 13
            total_duration = 58

        enriched_scenes = []
        for sc in scenes:
            prompt = build_scene_prompt(sc)
            enriched = dict(sc)
            enriched["vidu_prompt"] = prompt
            enriched["vidu_prompt_chars"] = prompt_char_count(prompt)
            enriched["vidu_duration_sec"] = max(3, min(int(sc.get("duration_sec", 15)), 16))
            enriched_scenes.append(enriched)

        merch_trigger = str(episode_meta.get("merch_punchline_trigger") or "Prompted This").strip()

        # Determine which scene naturally delivered the merch punchline trigger
        merch_scene = 4
        merch_lower = merch_trigger.lower()
        for sc in scenes:
            sc_id = int(sc.get("scene_id", 1))
            for line in (sc.get("dialogue") or []):
                if merch_lower in str(line.get("text") or "").lower():
                    merch_scene = sc_id
                    break

        return {
            "episode_id": episode_meta.get("episode_id", "ep_generated"),
            "episode_title": episode_meta.get("episode_title", "Untitled Episode"),
            "estimated_duration_sec": total_duration,
            "total_duration_sec": total_duration,
            "scene_count": len(enriched_scenes),
            "location": episode_meta.get("location", "Suburban Setting"),
            "merch_punchline_trigger": merch_trigger,
            "merch_context": f"Scene {merch_scene} delivers '{merch_trigger}'.",
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
        cast_characters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a production 4-scene script from the approved concept using OpenAI.
        Executes an automated 3-attempt retry loop with Agent M validation & logging.
        Zero static mock fallbacks. Dynamically passes all character details from Character Library.
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

        # Build dynamic character roster prompt from backend Character Library
        system_prompt, valid_ids = build_scriptwriter_system_prompt(cast_characters)
        valid_ids_str = ", ".join(valid_ids)

        max_retries = 3
        last_error = ""

        for attempt in range(1, max_retries + 1):
            logger.info("Agent 1: Scriptwriter generating script via OpenAI (%s) — attempt %d/%d...", model, attempt, max_retries)

            user_prompt = (
                f"Write a full 4-scene (56-58 second) CRASH OUT episodic script based on this approved concept:\n\n"
                f"HEADLINE: {headline}\n"
                f"CRASH-OUT NARRATIVE ANGLE: {angle}\n"
                f"PROPOSED MERCH HOOK: {merch_hook}\n"
                f"YOUTH TAKE: {youth_take}\n"
                f"SOURCES: {sources}\n\n"
                f"TIMING & SCENE DURATIONS: Exactly 4 scenes totaling 56–58 seconds. Scene 1: 15s, Scene 2: 15s, Scene 3: 15s, Scene 4: 11–13s (total 56–58s).\n"
                f"DIALOGUE PACING (BALANCED MEDIUM CADENCE): 3 to 4 well-paced dialogue turns per 15s scene (approx 20–30 spoken words per scene). Avoid rushed, frantic delivery, but do not write sparse 1-2 line scenes. Characters speak with witty comedic timing, reactions, and physical gestures.\n"
                f"CHARACTERS: Characters speaking from the registered roster ({valid_ids_str}). Actively engage characters across the scenes.\n"
                f"CINEMATIC DIRECTING CUES & 2000-CHAR BUDGET: Target 1500–1850 characters per scene. For EVERY dialogue turn, specify 'camera_cue' (camera movement/cut framing this speaker), 'action' (physical body gesture/expression while speaking), 'voice_tag' (vocal delivery), and 'sfx' (sound effect occurring on this turn).\n"
                f"MERCH HOOK: A speaking character must naturally deliver the exact merch hook: '{merch_hook}' in their dialogue in any scene (Scene 1, 2, 3, or 4)."
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
                    {"role": "system", "content": system_prompt},
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
                    retry_delay_sec = int(os.getenv("AGENT_RETRY_INTERVAL_SECONDS", "60"))
                    if attempt < max_retries:
                        logger.info("Agent 1: Waiting %ds (1 min) before retry attempt %d/%d...", retry_delay_sec, attempt + 1, max_retries)
                        time.sleep(retry_delay_sec)
                    continue

                content = (((resp.json() or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                parsed = self._parse_script_json(content)
                if not parsed or not parsed.get("scenes"):
                    last_error = f"OpenAI returned unparseable script JSON: {content[:150]}"
                    logger.warning("Agent 1 attempt %d parse failed: %s", attempt, last_error)
                    retry_delay_sec = int(os.getenv("AGENT_RETRY_INTERVAL_SECONDS", "60"))
                    if attempt < max_retries:
                        logger.info("Agent 1: Waiting %ds (1 min) before retry attempt %d/%d...", retry_delay_sec, attempt + 1, max_retries)
                        time.sleep(retry_delay_sec)
                    continue

                meta = {
                    "episode_id": episode_id or c.get("id") or "ep_generated",
                    "episode_title": headline,
                    "location": parsed.get("location") or "Suburban Setting",
                    "merch_punchline_trigger": parsed.get("merch_punchline_trigger") or merch_hook,
                    "source": f"openai_{model}",
                }
                candidate_script = self._flatten_scenes(parsed.get("scenes", []), meta, valid_ids=valid_ids)

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

            retry_delay_sec = int(os.getenv("AGENT_RETRY_INTERVAL_SECONDS", "60"))
            if attempt < max_retries:
                logger.info("Agent 1: Waiting %ds (1 min) before retry attempt %d/%d...", retry_delay_sec, attempt + 1, max_retries)
                time.sleep(retry_delay_sec)

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
