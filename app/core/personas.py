"""
CRASH OUT character bible + production episode templates.

Visuals are locked to the official 9:16 reference PNGs used by Vidu Q4 Preview.
Behavior / relationships follow the CRASH OUT Personas specification.
"""
from typing import Dict, Any, List

# Hard limit for Vidu prompt text (user/platform constraint for this pipeline).
VIDU_PROMPT_MAX_CHARS = 2000
SCENE_DURATION_SEC = 15
SCENE_COUNT = 4
EPISODE_DURATION_SEC = SCENE_DURATION_SEC * SCENE_COUNT  # 60s target (40–60 ok)

STYLE_SHORT = (
    "2D adult satirical cartoon series CRASH OUT, bold black outlines, flat cel-shading, "
    "expressive suburban comedy, 9:16 vertical."
)

CHARACTERS: Dict[str, Dict[str, Any]] = {
    "gary": {
        "id": "gary",
        "name": "Gary",
        "image_file": "gary.png",
        "age": 44,
        "role": "Father, suburban breadwinner, corporate middle-management drone",
        "archetype": "The Cracking Gentle Parent / Suburban MAGA Disciple",
        "guru": "Donald J. Trump",
        # Compact visual locked to reference PNG
        "visual_short": (
            "Gary 44 dad-bod, receding light-brown hair, huge tired eyes with dark bags, "
            "navy polo tucked into khaki pants, brown belt/shoes, glowing phone + cyan smartwatch, stressed."
        ),
        "visual_prompt": (
            "2D adult satirical animation. Gary, 44, pear-shaped dad build, receding light-brown hair, "
            "wide circular eyes with heavy dark bags, shocked open mouth. Navy short-sleeve polo tucked into "
            "khaki trousers, brown belt, dark brown loafers. Holds glowing smartphone; cyan-glow smartwatch on wrist."
        ),
        "psychological_profile": (
            "Wants to be an enlightened gentle parent who broke generational trauma, but under pressure "
            "shatters into Trumpian grievance politics. Terrified of irrelevance and financial ruin."
        ),
        "trigger": "Thermostat off 72F, utility waste, HOA fines, kids challenging his authority, stress-watch alerts.",
        "mannerisms": (
            "Starts soft therapist voice, then accordion-hand Trump rally cadence; jaw-clench; stress-watch panic."
        ),
        "lexicon": [
            "Holding space", "Emotional regulation", "Tremendous", "Witch hunt", "Rigged",
            "Tariffs", "Fake news", "Jira tickets",
        ],
        "voice": {
            "tone": "Soft therapist voice that spikes into nasal high-volume Trumpian hyperbole.",
            "speed": "1.15x",
            "audio_tag": "[Gary, stressed suburban dad]:",
        },
        "catchphrases": [
            "I am holding space for your feelings, but touch that thermostat and I tariff the Wi-Fi!",
            "The HOA fine is a total witch hunt!",
        ],
        "relations": {
            "chris": "Power struggle; Gary calls Chris lazy; Chris dismantles him with cold stats.",
            "chloe": "Gary fears Chloe; she records him and extracts beauty-product funding.",
            "linda": "Cold-war mutual delusion; therapy jargon instead of honesty.",
        },
    },
    "linda": {
        "id": "linda",
        "name": "Linda",
        "image_file": "linda.png",
        "age": 42,
        "role": "Mother, HOA/PTA social climber",
        "archetype": "The Secret Junk-Food Goopist / Status-Anxious Wellness Hypocrite",
        "guru": "Gwyneth Paltrow / Goop",
        "visual_short": (
            "Linda 42 slim, wavy honey-blonde hair, big eyes, forced smile, mauve/pink matching workout set, "
            "white sneakers, giant light-green Stanley tumbler with straw."
        ),
        "visual_prompt": (
            "2D adult satirical animation. Linda, 42, slim athletic build, shoulder-length wavy honey-blonde hair, "
            "large eyes with tired lines, wide toothy smile, white stud earrings. Matching mauve-pink sports bra and "
            "high-waisted leggings, white sneakers. Holds oversized light-green Stanley tumbler with straw."
        ),
        "psychological_profile": (
            "Preaches clean living and high vibration while secretly bingeing junk food and wine. "
            "Self-worth tied to neighborhood optics and Nextdoor reputation."
        ),
        "trigger": "Public aesthetic breaches, HOA judgment, group-chat screenshots, family looking 'off-brand'.",
        "mannerisms": (
            "Breathy faux-zen voice → shrill panic whisper; secret carb scarf; frantic hand-wipes for snack dust."
        ),
        "lexicon": [
            "Vibrational frequency", "Cellular detox", "Optics", "Nextdoor", "Toxic energy", "Abundance chakra",
        ],
        "voice": {
            "tone": "Breathy faux-zen that fractures into shrill status panic.",
            "speed": "1.05x",
            "audio_tag": "[Linda, breathy wellness panic]:",
        },
        "catchphrases": [
            "The optics of this family are below median HOA threshold!",
            "I am cleansed, I am light, I release judgment...",
        ],
        "relations": {
            "gary": "Hates his loud political bluster; weaponizes wellness critiques.",
            "chris": "Mortified by his posture and refusal of family photos.",
            "chloe": "Mutual blackmail over secret binges vs beauty funding.",
        },
    },
    "chris": {
        "id": "chris",
        "name": "Chris",
        "image_file": "chris.png",
        "age": 15,
        "role": "Son, high-school sophomore, bedroom nihilist",
        "archetype": "The Techno-Gospel Doomer / First Principles Bro",
        "guru": "Elon Musk / Simulation Theory",
        "visual_short": (
            "Chris 15, oversized charcoal hoodie with hood up, messy brown hair, half-lidded tired eyes, "
            "wired white earbuds, hands in kangaroo pocket, black sweatpants, black-and-white sneakers, deadpan."
        ),
        "visual_prompt": (
            "2D adult satirical animation. Chris, 15, slim teen, hood up on oversized charcoal hoodie, messy brown hair, "
            "heavy-lidded circular eyes, flat mouth. White wired earbuds, hands in front pocket, baggy black sweatpants, "
            "black-and-white sneakers. Completely deadpan."
        ),
        "psychological_profile": (
            "Anti-work apocalyptic about civilization yet dependent on dad's salary and wifi. "
            "Masks dread with cold statistical nihilism."
        ),
        "trigger": "Boomer advice, forced chores, interruptions during crypto/doomscroll.",
        "mannerisms": "Monotone drawl, no eye contact, indifferent shrug, speaks to walls/floors.",
        "lexicon": [
            "Late-stage capitalism", "NPC behavior", "Black-pilled", "First principles", "Entropy", "Simulation",
        ],
        "voice": {
            "tone": "Flat monotone teen drawl with zero emotional inflection.",
            "speed": "0.9x",
            "audio_tag": "[Chris, deadpan monotone]:",
        },
        "catchphrases": [
            "Statistically speaking, Gary, my chances of owning a house are zero.",
            "Human communication is a bandwidth-constrained legacy protocol.",
        ],
        "relations": {
            "gary": "Techno-nihilism vs MAGA hustle; proves Gary is getting poorer with data.",
            "linda": "Treats crystals/Goop as superstition; mocks calorie-to-cost ratios.",
            "chloe": "Despises her vanity but trades tech help for cash liquidity.",
        },
    },
    "chloe": {
        "id": "chloe",
        "name": "Chloe",
        "image_file": "chloe.png",
        "age": 11,
        "role": "Daughter, middle-schooler, de facto domestic business manager",
        "archetype": "The Pre-Teen Momager / Digital Monetization Shark",
        "guru": "Kris Jenner / Kardashian Dynasty",
        "visual_short": (
            "Chloe 11, brown pigtails with orange tips, mischievous smirk, color-block hoodie "
            "(purple/green/teal/pink), black joggers, rainbow charm Crocs, phone with glowing ring light."
        ),
        "visual_prompt": (
            "2D adult satirical animation. Chloe, 11, brown middle-part pigtails with orange-pink tips, large eyes, "
            "mischievous smirk. Color-block zip hoodie (purple/green/teal/pink/red), white tee, black joggers, "
            "rainbow Crocs with charms. Holds smartphone with circular glowing ring light."
        ),
        "psychological_profile": (
            "Cutthroat 45-year-old talent-manager instincts in an 11-year-old body. Family meltdowns are raw IP "
            "to package and monetize. Crashes out if algorithm downranks her."
        ),
        "trigger": "Shadowbans, bad lighting, clipped audio, interrupted livestreams.",
        "mannerisms": (
            "Pause-finger to silence parents, repositions ring light, flips from sugary influencer to cold PR shark."
        ),
        "lexicon": [
            "Cooked", "Major L", "Brand safety", "Retention", "Monetize the breakdown", "Link in bio",
        ],
        "voice": {
            "tone": "Sugary influencer vocal fry flipping into corporate PR cadence.",
            "speed": "1.15x",
            "audio_tag": "[Chloe, influencer smirk]:",
        },
        "catchphrases": [
            "Lower your voice, Gary, you're clipping my sponsored reel.",
            "Poll is live — link in bio for the merch drop!",
        ],
        "relations": {
            "gary": "Triggers his stress watch for algorithmic content gold.",
            "linda": "Blackmails with binge drafts for beauty funding.",
            "chris": "Monetizes his doomer aesthetic while ignoring collapse lectures.",
        },
    },
}


# Fixed production script from EPISODE SCRIPT: THE HOA VIOLATION (attached PDF).
# No LLM script model yet — Agent 1 always returns this package.
# Runtime ~55s across 4 beats. Vidu duration clamped to 3–16s per clip.
EPISODE_HOA_VIOLATION: Dict[str, Any] = {
    "episode_id": "hoa_violation_master",
    "episode_title": "The HOA Violation",
    "total_duration_sec": 55,
    "scene_count": SCENE_COUNT,
    "location": "The Pearson Family Kitchen, Suburban Home",
    "merch_punchline_trigger": "Capitalism broke my dad",
    "source": "EPISODE_SCRIPT__1_.pdf",
    "notes": [
        "Primary merch slogan: Capitalism broke my dad",
        "Chris secondary quote: It’s not gaslighting if I’m historically correct.",
        "Visual anchor: Chloe livestream UI → cracked-screen glitch → CRASH OUT logo",
    ],
    "scenes": [
        {
            "scene_id": 1,
            "title": "Hook & Setup",
            "time_range": "00:00 - 00:08",
            "time_start_sec": 0,
            "time_end_sec": 8,
            "duration_sec": 8,
            "primary_character": "gary",
            "characters": ["gary", "linda"],
            "camera_cue": (
                "WIDE SHOT on the kitchen. Gary front and center with laptop and tablet. "
                "Smartwatch flashes neon-red and beeps. Linda by fridge, half face frozen in Botox, "
                "gripping oversized Stanley Cup."
            ),
            "scene_action": (
                "Gary stands stressed with laptop/tablet as watch alarms. "
                "Linda plasters a strained frozen smile and sips through Stanley straw."
            ),
            "dialogue": [
                {
                    "character": "gary",
                    "text": (
                        "Linda, the HOA just hit us with a five-hundred-dollar fine. Five hundred! "
                        "I had to endure an extra hour of daily stand-ups with a 23-year-old engineering "
                        "manager just to fund this!"
                    ),
                    "voice_tag": "[Gary, voice trembling, sleep-deprived eyes wide]:",
                },
                {
                    "character": "linda",
                    "text": "Gary, deep breaths. We are operating in gratitude. What could they have possibly done?",
                    "voice_tag": "[Linda, strained frozen smile, sipping Stanley straw]:",
                },
                {
                    "character": "gary",
                    "text": (
                        "They spray-painted a massive mural on our garage door of me weeping over my bank account, "
                        'tagged with: "Capitalism broke my dad."'
                    ),
                    "voice_tag": "[Gary, cracking humiliation]:",
                },
            ],
            "sfx": "smartwatch neon-red alarm beeps, Stanley straw sip",
        },
        {
            "scene_id": 2,
            "title": "Conflict & Escalation",
            "time_range": "00:09 - 00:22",
            "time_start_sec": 9,
            "time_end_sec": 22,
            "duration_sec": 14,
            "primary_character": "chloe",
            "characters": ["chloe", "chris", "gary"],
            "camera_cue": (
                "Kitchen door swings open. Chris in oversized hoodie eats dry cereal from the box. "
                "Chloe walks in with phone mounted on an active ring light pointed at Gary."
            ),
            "scene_action": (
                "Chloe livestreams Gary with glowing ring light. Gary hysterically screams at camera. "
                "Chris deadpan-crunches cereal without blinking."
            ),
            "dialogue": [
                {
                    "character": "chloe",
                    "text": (
                        "What's up, guys! Today we're testing how fast an over-leveraged suburban dad develops "
                        "a live-streamed stroke. Tap that plus button to see if the forehead vein pops!"
                    ),
                    "voice_tag": "[Chloe, angelic breathy influencer voice into phone]:",
                },
                {
                    "character": "gary",
                    "text": (
                        "Chloe! Kill the camera! Chris, did you breach the neighborhood Wi-Fi network and leak "
                        "your mother's therapy session transcripts directly into the HOA Facebook group?!"
                    ),
                    "voice_tag": "[Gary, hysterical scream]:",
                },
                {
                    "character": "chris",
                    "text": (
                        "First off, that wasn't a leak; it was open-sourcing mental wellness. Second, your current "
                        "reaction just spiked our engagement by 40%. It's not gaslighting if I'm historically correct."
                    ),
                    "voice_tag": "[Chris, completely deadpan, crunching cereal]:",
                },
            ],
            "sfx": "cereal crunch, livestream chimes, ring-light hum",
        },
        {
            "scene_id": 3,
            "title": "The Crack / Breakdown",
            "time_range": "00:23 - 00:38",
            "time_start_sec": 23,
            "time_end_sec": 38,
            "duration_sec": 16,
            "primary_character": "linda",
            "characters": ["gary", "linda"],
            "camera_cue": (
                "CLOSE-UP on Gary's smartwatch flashing 185 BPM CRITICAL STRESS. "
                "Cut to Linda's neurotic blinking with paralyzed Botox forehead, then pantry cabinet."
            ),
            "scene_action": (
                "Gary clutches his head. Linda panics, yanks a hidden bottom cabinet, rips open a family-size "
                "junk-food bag, shoves a massive handful into her mouth, and mumbles affirmations."
            ),
            "dialogue": [
                {
                    "character": "gary",
                    "text": (
                        "Open-sourcing?! I work myself into the ground funding your lives just for you to turn "
                        "this family's clinical depression into a TikTok trend?!"
                    ),
                    "voice_tag": "[Gary, clutching head, choked up]:",
                },
                {
                    "character": "linda",
                    "text": (
                        "Mrs. Higgins already sent me a screenshot on WhatsApp... Our optics are completely "
                        "shattered. The energetic frequency is poisoned."
                    ),
                    "voice_tag": "[Linda, rapid neurotic blinking, lips twitching]:",
                },
                {
                    "character": "linda",
                    "text": "I am aligned. I am worthy. Universe, absorb the carbs.",
                    "voice_tag": "[Linda, mouth full, manic whisper]:",
                },
            ],
            "sfx": "heart-monitor critical alert, cabinet yank, snack-bag crinkle, frantic chewing",
        },
        {
            "scene_id": 4,
            "title": "Merch Punchline & Outro",
            "time_range": "00:39 - 00:55",
            "time_start_sec": 39,
            "time_end_sec": 55,
            "duration_sec": 16,
            "primary_character": "chloe",
            "characters": ["chloe", "chris", "gary", "linda"],
            "camera_cue": (
                "Chloe pans livestream smoothly from Linda binging junk food to Gary clutching his skull. "
                "Chris peeks over her shoulder. End on violent glitch crack into bold CRASH OUT logo."
            ),
            "scene_action": (
                "Chloe delivers merch poll with sinister grin. Chris deadpans Shopify jab. "
                "Gary silent agonized scream in background. Screen glitches/cracks to CRASH OUT logo sting."
            ),
            "dialogue": [
                {
                    "character": "chloe",
                    "text": (
                        "Alright chat, poll is live: What gives out first? Mom's Botox, or Dad's mortgage? "
                        'Link in bio for the official "Capitalism broke my dad" drop!'
                    ),
                    "voice_tag": "[Chloe, directly to camera, sinister grin]:",
                },
                {
                    "character": "chris",
                    "text": "Cop it now, before Gary realizes his checking account is wired straight to Shopify.",
                    "voice_tag": "[Chris, peeking over shoulder, deadpan stare]:",
                },
            ],
            "sfx": "heart flatline monitor tone, harsh digital glass shatter, glitch static",
        },
    ],
}


def is_known_character(char_id: str) -> bool:
    cid = (char_id or "").lower().strip()
    if cid in CHARACTERS:
        return True
    try:
        from app.studio.characters import load_library
        chars = load_library().get("characters") or {}
        return cid in chars
    except Exception:
        return False


def characters_in_scene(scene: Dict[str, Any]) -> List[str]:
    """Ordered unique cast for a scene (primary first). Supports dynamic character library."""
    ordered: List[str] = []
    primary = str(scene.get("primary_character", "")).lower().strip()
    if primary and is_known_character(primary):
        ordered.append(primary)
    for cid in scene.get("characters", []) or []:
        c = str(cid).lower().strip()
        if c and is_known_character(c) and c not in ordered:
            ordered.append(c)
    for line in scene.get("dialogue", []) or []:
        c = str(line.get("character", "")).lower().strip()
        if c and is_known_character(c) and c not in ordered:
            ordered.append(c)
    return ordered or ["gary"]


def get_vidu_system_style_prefix() -> str:
    return STYLE_SHORT


def get_vidu_character_persona_prompt(char_id: str, script_text: str = "") -> str:
    c = CHARACTERS.get(char_id.lower(), CHARACTERS["gary"])
    tag = c["voice"]["audio_tag"]
    base = f"{STYLE_SHORT} {c['visual_short']} Action: {c['mannerisms']}"
    if script_text:
        return f'{base} Native audio: {tag} "{script_text}"'[:VIDU_PROMPT_MAX_CHARS]
    return base[:VIDU_PROMPT_MAX_CHARS]
