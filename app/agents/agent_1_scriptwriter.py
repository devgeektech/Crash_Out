"""
Agent 1: Script package builder.

No LLM script model yet — returns a fixed package selected by script_key:
  - hoa_violation: original attached PDF script
  - hoa_q4_prompts: attached Prompt_1–Prompt_4 Vidu pack
"""
from typing import Dict, Any, List, Optional

from app.core.catalog import get_hoa_q4_prompt_episode, get_script_package_for_key
from app.core.personas import EPISODE_HOA_VIOLATION
from app.core.prompts import build_scene_prompt, prompt_char_count


class Agent1Scriptwriter:
    def __init__(self):
        self.name = "Agent 1 (Fixed Script Package)"

    def _package_for(self, script_key: str) -> Dict[str, Any]:
        if script_key == "hoa_q4_prompts":
            return get_hoa_q4_prompt_episode()
        custom = get_script_package_for_key(script_key)
        if custom:
            return custom
        return EPISODE_HOA_VIOLATION

    def _flatten_scenes(
        self,
        scenes: List[Dict[str, Any]],
        episode_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        flat_lines = []
        line_idx = 1
        for sc in scenes:
            sc_id = int(sc.get("scene_id", 1))
            base_time = float(sc.get("time_start_sec", (sc_id - 1) * 15))
            duration = float(sc.get("duration_sec", 15))
            lines = sc.get("dialogue", []) or []
            sub_step = duration / max(len(lines), 1)
            for d_i, d in enumerate(lines):
                flat_lines.append(
                    {
                        "index": line_idx,
                        "scene_id": sc_id,
                        "character": d["character"],
                        "time_start": round(base_time + d_i * sub_step, 1),
                        "time_end": round(base_time + (d_i + 1) * sub_step, 1),
                        "camera_cue": sc.get("camera_cue", ""),
                        "text": d["text"],
                        "emotion": d.get("voice_tag", ""),
                        "vidu_action": sc.get("scene_action", ""),
                    }
                )
                line_idx += 1

        enriched_scenes = []
        for sc in scenes:
            prompt = build_scene_prompt(sc)
            enriched = dict(sc)
            enriched["vidu_prompt"] = prompt
            enriched["vidu_prompt_chars"] = prompt_char_count(prompt)
            enriched["vidu_duration_sec"] = max(3, min(int(sc.get("duration_sec", 15)), 16))
            enriched_scenes.append(enriched)

        total = int(episode_meta.get("total_duration_sec", 55))
        return {
            "episode_id": episode_meta.get("episode_id", "hoa_violation_master"),
            "episode_title": episode_meta.get("episode_title", "The HOA Violation"),
            "estimated_duration_sec": total,
            "total_duration_sec": total,
            "scene_count": len(enriched_scenes),
            "location": episode_meta.get(
                "location", "The Pearson Family Kitchen, Suburban Home"
            ),
            "merch_punchline_trigger": episode_meta.get(
                "merch_punchline_trigger", "Capitalism broke my dad"
            ),
            "merch_context": episode_meta.get(
                "merch_context",
                "Garage mural + Chloe livestream poll for Capitalism broke my dad drop.",
            ),
            "source": episode_meta.get("source", "fixed_pdf_script"),
            "script_key": episode_meta.get("script_key", "hoa_violation"),
            "notes": episode_meta.get("notes", []),
            "scenes": enriched_scenes,
            "dialogue_lines": flat_lines,
            "prompt_budget_chars": 2000,
            "script_mode": "fixed_package",
        }

    def generate_script(self, concept: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        script_key = "hoa_violation"
        if concept and concept.get("script_key"):
            script_key = str(concept.get("script_key"))
        package = self._package_for(script_key)
        meta = {
            **package,
            "script_key": script_key,
            "merch_context": (
                "Garage mural humiliation and Chloe's livestream merch poll for "
                '"Capitalism broke my dad".'
            ),
        }
        if concept and concept.get("title"):
            meta["selected_concept_title"] = concept.get("title")
            meta["episode_title"] = concept.get("title") or meta.get("episode_title")
        return self._flatten_scenes(package["scenes"], meta)


scriptwriter_agent = Agent1Scriptwriter()
