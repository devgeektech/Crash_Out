"""
Production catalog: selectable videos that open into the HITL pipeline at Gate 1.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from app.paths import OUTPUT_DIR, PROJECT_ROOT

DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
CUSTOM_CATALOG_FILE = os.path.join(OUTPUT_DIR, "custom_catalog.json")

PROMPT_FILES = [
    "Prompt_1_0000_0015.txt",
    "Prompt_2_0015_0030.txt",
    "Prompt_3_0030_0045..txt",  # filename includes double-dot as provided
    "Prompt_4_0045_0055.txt",
]


def prompt_file_path(filename: str) -> str:
    """Prefer docs/ prompt packs; fall back to outputs/ for legacy saves."""
    docs_path = os.path.join(DOCS_DIR, filename)
    if os.path.exists(docs_path):
        return docs_path
    return os.path.join(OUTPUT_DIR, filename)


def _read_prompt(filename: str) -> str:
    path = prompt_file_path(filename)
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().strip()


def load_q4_prompt_texts() -> List[str]:
    return [_read_prompt(name) for name in PROMPT_FILES]


def build_hoa_q4_prompt_episode() -> Dict[str, Any]:
    """Second catalog script: attached Vidu prompt files (15/15/15/10)."""
    texts = load_q4_prompt_texts()
    durations = [15, 15, 15, 10]
    # Titles follow the attached prompt clip ranges (not story beat labels).
    titles = [
        "Clip 1 · 00:00–00:15",
        "Clip 2 · 00:15–00:30",
        "Clip 3 · 00:30–00:45",
        "Clip 4 · 00:45–00:55",
    ]
    primaries = ["gary", "chloe", "linda", "chloe"]
    casts = [
        ["gary", "linda", "chloe", "chris"],
        ["gary", "linda", "chloe", "chris"],
        ["gary", "linda", "chloe", "chris"],
        ["gary", "linda", "chloe", "chris"],
    ]
    dialogue = [
        [
            {
                "character": "gary",
                "text": (
                    "Linda, the HOA just hit us with a five-hundred-dollar fine. Five hundred! "
                    "I had to endure an extra hour of daily stand-ups with a 23-year-old engineering "
                    "manager just to fund this!"
                ),
                "voice_tag": "[Gary, exhausted, trembling]:",
            },
            {
                "character": "linda",
                "text": "Gary, deep breaths. We are operating in gratitude. What could they have possibly done?",
                "voice_tag": "[Linda, frozen smile]:",
            },
            {
                "character": "gary",
                "text": (
                    "They spray-painted a massive mural on our garage door of me weeping over my bank account, "
                    "tagged with: 'Capitalism broke my dad.'"
                ),
                "voice_tag": "[Gary, blotchy red, chopping the air]:",
            },
        ],
        [
            {
                "character": "chloe",
                "text": (
                    "What's up, guys! Today we're testing how fast an over-leveraged suburban dad develops "
                    "a live-streamed stroke. Tap that plus button to see if the forehead vein pops!"
                ),
                "voice_tag": "[Chloe, sugary influencer voice]:",
            },
            {
                "character": "gary",
                "text": (
                    "Chloe! Kill the camera! Chris, did you breach the neighborhood Wi-Fi network and leak "
                    "your mother's therapy session transcripts directly into the HOA Facebook group?!"
                ),
                "voice_tag": "[Gary, exploding]:",
            },
            {
                "character": "chris",
                "text": (
                    "First off, that wasn't a leak; it was open-sourcing mental wellness. Second, your current "
                    "reaction just spiked our engagement by 40%. It's not gaslighting if I'm historically correct."
                ),
                "voice_tag": "[Chris, cold flat monotone]:",
            },
        ],
        [
            {
                "character": "gary",
                "text": (
                    "Open-sourcing?! I work myself into the ground funding your lives just for you to turn "
                    "this family's clinical depression into a TikTok trend?!"
                ),
                "voice_tag": "[Gary, exaggerated rally-style intensity]:",
            },
            {
                "character": "linda",
                "text": (
                    "Mrs. Higgins already sent me a screenshot on WhatsApp... Our optics are completely shattered. "
                    "The energetic frequency is poisoned."
                ),
                "voice_tag": "[Linda, eyelids twitching]:",
            },
        ],
        [
            {
                "character": "linda",
                "text": "I am aligned. I am worthy. Universe, absorb the carbs.",
                "voice_tag": "[Linda, stuffed cheeks, frantic whisper]:",
            },
            {
                "character": "chloe",
                "text": (
                    "Alright chat, poll is live: What gives out first? Mom's Botox, or Dad's mortgage? "
                    "Link in bio for the official 'Capitalism broke my dad' drop!"
                ),
                "voice_tag": "[Chloe, sugary commercial voice]:",
            },
            {
                "character": "chris",
                "text": "Cop it now, before Gary realizes his checking account is wired straight to Shopify.",
                "voice_tag": "[Chris, expressionless]:",
            },
        ],
    ]
    actions = [
        "Gary at island with red watch alarm; Linda sips Stanley; mural insert; Chloe and Chris enter.",
        "Chloe livestreams Gary; Gary explodes at kids; Chris deadpans cereal engagement math.",
        "Watch hits 185 BPM; Gary explodes; Linda panics and binges junk food from hidden cabinet.",
        "Linda affirmation binge; Chloe merch poll; Chris Shopify jab; cracked-screen CRASH OUT sting.",
    ]
    cameras = [
        "Wide kitchen → push-in on Gary → mural insert → door opens on Chloe/Chris.",
        "Continue from Clip 1 end frame; Chloe ring-light phone on Gary; Chris cereal foreground.",
        "Extreme CU watch → Gary head-clutch → Linda twitch → lower cabinet binge; Chloe phone follows.",
        "Linda chewing → Chloe to phone → Chris over shoulder → Gary silent scream → glitch to logo.",
    ]
    sfx = [
        "watch beeps, whoosh, door, cereal crunch",
        "cereal crunch, livestream notifications, kitchen ambience",
        "watch alarm, escalating shout, anxious breath, cabinet slam, snack-bag crinkle",
        "snack crinkle, livestream chimes, heart-monitor flatline, digital glass shatter",
    ]

    scenes = []
    t = 0
    for i, dur in enumerate(durations):
        scenes.append(
            {
                "scene_id": i + 1,
                "title": titles[i],
                "time_range": _time_range(t, t + dur),
                "time_start_sec": t,
                "time_end_sec": t + dur,
                "duration_sec": dur,
                "primary_character": primaries[i],
                "characters": casts[i],
                "camera_cue": cameras[i],
                "scene_action": actions[i],
                "dialogue": dialogue[i],
                "sfx": sfx[i],
                "source_prompt": texts[i],
                "source_prompt_file": PROMPT_FILES[i],
            }
        )
        t += dur

    return {
        "episode_id": "hoa_violation_q4_prompts",
        "episode_title": "The HOA Violation (Q4 Prompt Cut)",
        "total_duration_sec": 55,
        "scene_count": 4,
        "location": "The Pearson Family Kitchen, Suburban Home",
        "merch_punchline_trigger": "Capitalism broke my dad",
        "source": "docs/Prompt_1..4",
        "script_key": "hoa_q4_prompts",
        "notes": [
            "Built from docs/ Vidu prompt files Prompt_1–Prompt_4",
            "Clip lengths: 15 / 15 / 15 / 10 seconds",
            "source_prompt on each scene is sent to Vidu as written",
        ],
        "scenes": scenes,
    }


def _time_range(start: int, end: int) -> str:
    def fmt(sec: int) -> str:
        return f"{sec // 60:02d}:{sec % 60:02d}"

    return f"{fmt(start)} - {fmt(end)}"


# Lazy-built so missing files fail only when opening video 2
_EPISODE_HOA_Q4_CACHE: Optional[Dict[str, Any]] = None


def get_hoa_q4_prompt_episode() -> Dict[str, Any]:
    global _EPISODE_HOA_Q4_CACHE
    if _EPISODE_HOA_Q4_CACHE is None:
        _EPISODE_HOA_Q4_CACHE = build_hoa_q4_prompt_episode()
    return _EPISODE_HOA_Q4_CACHE


def refresh_hoa_q4_prompt_episode() -> Dict[str, Any]:
    """Rebuild from disk prompt files (after edits or title changes)."""
    global _EPISODE_HOA_Q4_CACHE
    _EPISODE_HOA_Q4_CACHE = build_hoa_q4_prompt_episode()
    return _EPISODE_HOA_Q4_CACHE


VIDEO_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "hoa_violation",
        "script_key": "hoa_violation",
        "title": "The HOA Violation",
        "subtitle": "Dad's $500 mural meltdown",
        "duration_label": "~55s · 8/14/16/16",
        "status_label": "Ready to produce",
        "premise": (
            "Gary gets a $500 HOA fine after a garage mural of him weeping over his bank account. "
            "Chloe livestreams the crash-out; Chris open-sources therapy notes; Linda binge-affirms."
        ),
        "merch": "Capitalism broke my dad",
        "concept": {
            "id": "concept_1",
            "title": "The HOA Violation: Dad's $500 Mural Meltdown",
            "cultural_hook": (
                "Suburban HOA tyranny meets TikTok parent-shaming and the hustle of turning "
                "family humiliation into merch before the fine is even paid."
            ),
            "premise": (
                "Gary Pearson opens a $500 HOA fine on his smartwatch and immediately spirals: "
                "someone spray-painted a garage mural of him weeping over a bank statement, "
                "tagged with the phrase that will soon become a merch drop — "
                "'Capitalism broke my dad.' Linda tries to reframe the crisis as a gratitude "
                "exercise while sipping from her Stanley tumbler. Chloe kicks off a livestream "
                "to crowd-test how fast Dad's forehead vein pops, and Chris admits he "
                "'open-sourced' Linda's therapy notes into the HOA Facebook group for engagement. "
                "The kitchen becomes a 55-second crash-out: watch alarms, moral lectures, "
                "snack-cabinet bingeing, a live Shopify poll, and a cracked-screen CRASH OUT sting."
            ),
            "synopsis": (
                "A vertical satirical sitcom beat where financial shame, performative wellness, "
                "and teenage content extraction collide in one suburban kitchen. The HOA fine is "
                "the fuse; the mural is the humiliation; the kids treat both as inventory."
            ),
            "characters_involved": ["gary", "linda", "chris", "chloe"],
            "suggested_merch": "Capitalism broke my dad",
            "conflict": (
                "Gary fights the $500 fine and his children's content machine while Linda "
                "protects optics and emotional branding over the actual bank account."
            ),
            "tone": "Fast-paced satirical suburban escalation — South Park bite, Arrested Development irony",
            "script_key": "hoa_violation",
        },
    },
    {
        "id": "hoa_q4_prompts",
        "script_key": "hoa_q4_prompts",
        "title": "The HOA Violation (Q4 Prompt Cut)",
        "subtitle": "Attached Vidu prompt pack",
        "duration_label": "~55s · 15/15/15/10",
        "status_label": "Ready to produce",
        "premise": (
            "Same kitchen crash-out, rebuilt from Prompt_1–Prompt_4 for Vidu Q4 continuity cuts "
            "with locked character boards and cracked-screen outro."
        ),
        "merch": "Capitalism broke my dad",
        "concept": {
            "id": "concept_hoa_q4",
            "title": "The HOA Violation (Q4 Prompt Cut)",
            "cultural_hook": (
                "Continuity-locked Vidu Q4 reference2video pack: four timed kitchen clips that "
                "keep Pearson looks, outfits, and layout identical while the HOA fine, livestream, "
                "and merch drop escalate in sequence."
            ),
            "premise": (
                "Clip 1 (00:00–00:15) hooks on Gary's watch alarm and the $500 fine, with a brief "
                "garage-mural insert of weeping cartoon Gary. Clip 2 (00:15–00:30) continues from "
                "Chloe entering with her ring-light phone; Gary detonates at the kids while Chris "
                "deadpans that leaking therapy notes was 'open-sourcing mental wellness.' "
                "Clip 3 (00:30–00:45) spikes the watch to 185 BPM, Linda's Botox smile cracks into "
                "WhatsApp optics panic, then she binge-eats from a hidden cabinet on camera. "
                "Clip 4 (00:45–00:55) lands the merch poll — Mom's Botox vs Dad's mortgage — "
                "Chris plugs Shopify, and the frame glitches into the CRASH OUT logo."
            ),
            "synopsis": (
                "Production-ready Q4 cut of the HOA Violation: 15/15/15/10 seconds, character lock "
                "boards, end-frame handoffs between clips, and a cracked-screen logo sting — "
                "built so Vidu reference images carry visual identity while the prompt pack "
                "carries dialogue, SFX, and timing."
            ),
            "characters_involved": ["gary", "linda", "chris", "chloe"],
            "suggested_merch": "Capitalism broke my dad",
            "conflict": (
                "Gary vs the HOA fine, Chloe's livestream, Chris's engagement math, and Linda's "
                "performative wellness — all locked for four continuous Q4 clips."
            ),
            "tone": "Continuity-locked satirical Q4 prompt cut with snappy kitchen escalation",
            "script_key": "hoa_q4_prompts",
        },
    },
]


def _load_custom_catalog() -> List[Dict[str, Any]]:
    if not os.path.exists(CUSTOM_CATALOG_FILE):
        return []
    try:
        with open(CUSTOM_CATALOG_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        items = data.get("items") if isinstance(data, dict) else data
        return list(items or [])
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def _save_custom_catalog(items: List[Dict[str, Any]]) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(CUSTOM_CATALOG_FILE, "w", encoding="utf-8") as fh:
        json.dump({"items": items}, fh, indent=2)


DELETED_CATALOG_FILE = os.path.join(OUTPUT_DIR, "deleted_catalog.json")


def _load_deleted_builtin_ids() -> set[str]:
    if not os.path.exists(DELETED_CATALOG_FILE):
        return set()
    try:
        with open(DELETED_CATALOG_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return set(data if isinstance(data, list) else data.get("ids", []))
    except Exception:
        return set()


def _save_deleted_builtin_id(item_id: str) -> None:
    current = _load_deleted_builtin_ids()
    current.add(item_id)
    try:
        with open(DELETED_CATALOG_FILE, "w", encoding="utf-8") as fh:
            json.dump(list(current), fh, indent=2)
    except Exception:
        pass


def list_catalog_items(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Built-in catalog first, then manually added videos (scoped by user_id if provided)."""
    deleted_ids = _load_deleted_builtin_ids()
    builtins = [it for it in VIDEO_CATALOG if it.get("id") not in deleted_ids]
    # Built-ins are only shown if not deleted
    custom_items = _load_custom_catalog()
    if user_id is not None:
        custom_items = [it for it in custom_items if it.get("user_id") == int(user_id)]
    return builtins + custom_items


def get_catalog_item(catalog_id: str) -> Optional[Dict[str, Any]]:
    for item in list_catalog_items():
        if item.get("id") == catalog_id:
            return item
    return None


def build_manual_script_package(
    *,
    title: str,
    catalog_id: str,
    merch: str = "Capitalism broke my dad",
) -> Dict[str, Any]:
    """Blank editable 4-clip prompt pack for manually added videos."""
    durations = [15, 15, 15, 10]
    titles = [
        "Clip 1 · 00:00–00:15",
        "Clip 2 · 00:15–00:30",
        "Clip 3 · 00:30–00:45",
        "Clip 4 · 00:45–00:55",
    ]
    scenes = []
    t = 0
    for i, dur in enumerate(durations):
        placeholder = (
            f"SCENE {i + 1} — {titles[i]}\n\n"
            "Write the full Vidu prompt for this clip here.\n"
            "Keep Pearson family looks locked via reference images."
        )
        scenes.append(
            {
                "scene_id": i + 1,
                "title": titles[i],
                "time_range": _time_range(t, t + dur),
                "time_start_sec": t,
                "time_end_sec": t + dur,
                "duration_sec": dur,
                "primary_character": "gary",
                "characters": ["gary", "linda", "chris", "chloe"],
                "camera_cue": "Kitchen continuity, 9:16.",
                "scene_action": "Manual scene — edit prompt before generate.",
                "dialogue": [
                    {
                        "character": "gary",
                        "text": f"(Scene {i + 1} dialogue — edit in prompt)",
                        "voice_tag": "neutral",
                    }
                ],
                "sfx": "",
                "source_prompt": placeholder,
            }
        )
        t += dur

    return {
        "episode_id": catalog_id,
        "episode_title": title,
        "total_duration_sec": 55,
        "scene_count": 4,
        "location": "The Pearson Family Kitchen, Suburban Home",
        "merch_punchline_trigger": merch,
        "source": "manual_add",
        "script_key": catalog_id,
        "notes": ["Manually added video — edit scene prompts before Generate Video"],
        "scenes": scenes,
    }


def add_manual_catalog_video(
    title: str,
    subtitle: str = "",
    merch: str = "Capitalism broke my dad",
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Append a user-created video to the catalog (newest = highest list number)."""
    clean_title = (title or "").strip() or "Untitled video"
    clean_sub = (subtitle or "").strip() or "Manual video"
    clean_merch = (merch or "").strip() or "Capitalism broke my dad"
    slug = re.sub(r"[^a-z0-9]+", "_", clean_title.lower()).strip("_") or "video"
    catalog_id = f"custom_{slug}_{int(time.time())}"

    item = {
        "id": catalog_id,
        "user_id": user_id,
        "script_key": catalog_id,
        "title": clean_title,
        "subtitle": clean_sub,
        "duration_label": "~55s · 15/15/15/10",
        "status_label": "Ready to produce",
        "premise": clean_sub,
        "merch": clean_merch,
        "custom": True,
        "created_at": time.time(),
        "script_package": build_manual_script_package(
            title=clean_title, catalog_id=catalog_id, merch=clean_merch
        ),
        "concept": {
            "id": f"concept_{catalog_id}",
            "title": clean_title,
            "headline": clean_title,
            "cultural_hook": "",
            "youth_sentiment_summary": "",
            "premise": "",
            "crash_out_angle": "",
            "synopsis": "",
            "conflict": "",
            "tone": "",
            "suggested_merch": "",
            "proposed_merch_hook": "",
            "characters_involved": ["gary", "linda", "chris", "chloe"],
            "script_key": catalog_id,
            "manual": True,
            "empty": False,
        },
    }
    items = _load_custom_catalog()
    items.append(item)
    _save_custom_catalog(items)
    return item


def get_script_package_for_key(script_key: str) -> Optional[Dict[str, Any]]:
    """Return a stored script package for custom catalog keys."""
    item = get_catalog_item(script_key)
    if not item:
        return None
    pkg = item.get("script_package")
    return dict(pkg) if isinstance(pkg, dict) else None


def update_custom_scene_prompt(catalog_id: str, scene_id: int, source_prompt: str) -> bool:
    """Persist edited prompt back into a manually added catalog package."""
    items = _load_custom_catalog()
    changed = False
    for item in items:
        if item.get("id") != catalog_id:
            continue
        pkg = item.get("script_package") or {}
        scenes = pkg.get("scenes") or []
        for sc in scenes:
            if int(sc.get("scene_id", 0)) == int(scene_id):
                sc["source_prompt"] = source_prompt
                sc["vidu_prompt"] = source_prompt
                changed = True
                break
        if changed:
            item["script_package"] = pkg
            break
    if changed:
        _save_custom_catalog(items)
    return changed


def delete_manual_catalog_video(catalog_id: str) -> bool:
    """Remove a catalog video (custom or built-in)."""
    items = _load_custom_catalog()
    kept = [item for item in items if item.get("id") != catalog_id]
    if len(kept) != len(items):
        _save_custom_catalog(kept)
        return True
    # If not in custom catalog, check built-in and mark as deleted
    for it in VIDEO_CATALOG:
        if it.get("id") == catalog_id:
            _save_deleted_builtin_id(catalog_id)
            return True
    return False


def empty_concept(slot: int, *, script_key: Optional[str] = None, manual: bool = False) -> Dict[str, Any]:
    """Blank Gate 1 slot — headings only in UI, no sample body copy."""
    return {
        "id": f"empty_{slot}",
        "title": "",
        "headline": "",
        "premise": "",
        "crash_out_angle": "",
        "cultural_hook": "",
        "youth_sentiment_summary": "",
        "synopsis": "",
        "conflict": "",
        "tone": "",
        "suggested_merch": "",
        "proposed_merch_hook": "",
        "characters_involved": ["gary", "linda", "chris", "chloe"],
        "empty": True,
        "manual": bool(manual),
        "script_key": script_key,
    }


def _sanitize_manual_concept(concept: Dict[str, Any], *, script_key: str, title_fallback: str = "") -> Dict[str, Any]:
    """Strip legacy sample filler from manual catalog concepts."""
    c = dict(concept or {})
    sample_blobs = {
        "manual video",
        "manual concept",
        "editable prompt pack",
        "capitalism broke my dad",
    }

    def _clean(value: Any) -> str:
        text = str(value or "").strip()
        return "" if text.lower() in sample_blobs else text

    title = _clean(c.get("headline") or c.get("title")) or (title_fallback or "").strip()
    return {
        **c,
        "id": c.get("id") or f"concept_{script_key}",
        "title": title,
        "headline": title,
        "cultural_hook": _clean(c.get("cultural_hook")),
        "youth_sentiment_summary": _clean(c.get("youth_sentiment_summary")),
        "premise": _clean(c.get("premise")),
        "crash_out_angle": _clean(c.get("crash_out_angle")),
        "synopsis": _clean(c.get("synopsis")),
        "conflict": _clean(c.get("conflict")),
        "tone": _clean(c.get("tone")),
        "suggested_merch": _clean(c.get("suggested_merch")),
        "proposed_merch_hook": _clean(c.get("proposed_merch_hook")),
        "characters_involved": c.get("characters_involved")
        or ["gary", "linda", "chris", "chloe"],
        "script_key": script_key,
        "manual": True,
        "empty": not bool(title),
    }


def concepts_for_catalog(catalog_id: str) -> List[Dict[str, Any]]:
    """
    Gate 1 concept cards for a catalog video.
    Manual / custom + Q4: one primary editable card + two blank editable slots.
    Built-in HOA: Agent 0 friction pitches (Top 5).
    """
    from app.agents.agent_0_trend_ingest import trend_ingest_agent

    item = get_catalog_item(catalog_id)
    if not item:
        return [
            empty_concept(1, manual=True),
            empty_concept(2, manual=True),
            empty_concept(3, manual=True),
        ]

    if catalog_id == "hoa_q4_prompts" or item.get("custom"):
        primary = _sanitize_manual_concept(
            dict(item.get("concept") or {}),
            script_key=str(item.get("script_key") or catalog_id),
            title_fallback=str(item.get("title") or ""),
        )
        return [
            primary,
            empty_concept(2, script_key=str(item.get("script_key") or catalog_id), manual=True),
            empty_concept(3, script_key=str(item.get("script_key") or catalog_id), manual=True),
        ]

    concepts = trend_ingest_agent.fetch_trending_concepts()
    return concepts


def is_empty_concept(concept: Optional[Dict[str, Any]]) -> bool:
    if not concept:
        return True
    if bool(concept.get("empty")):
        # Allow approving a manual blank only after the user filled a title/headline.
        title = (concept.get("headline") or concept.get("title") or "").strip()
        if concept.get("manual") and title:
            return False
        return True
    return (concept.get("title") or concept.get("headline") or "").strip().lower() == "empty"


def update_catalog_concept(catalog_id: str, concept: Dict[str, Any]) -> bool:
    """Persist edits to a custom catalog item's primary concept card."""
    items = _load_custom_catalog()
    changed = False
    for item in items:
        if item.get("id") != catalog_id:
            continue
        item["concept"] = _sanitize_manual_concept(
            concept,
            script_key=str(item.get("script_key") or catalog_id),
            title_fallback=str(concept.get("headline") or concept.get("title") or item.get("title") or ""),
        )
        # Keep queue title in sync when the primary concept headline changes.
        new_title = str(item["concept"].get("title") or "").strip()
        if new_title:
            item["title"] = new_title
        changed = True
        break
    if changed:
        _save_custom_catalog(items)
    return changed
