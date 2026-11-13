"""
Agent 4: Multi-Channel Publishing & Merch Deployment Agent.
Generates algorithm-optimized metadata for YouTube Shorts, TikTok, and IG Reels,
plus auto-renders live T-Shirt / Hoodie print mockups using the episode's Merch Trigger.
"""
import os
import time
from typing import Dict, Any
from PIL import Image, ImageDraw, ImageFont

from app.paths import episode_dir, ensure_episode_output_folder, public_url

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "assets", "templates")

def get_font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()

class Agent4Publisher:
    def __init__(self):
        self.name = "Agent 4 (Publishing & Merch Deployment)"

    def generate_merch_mockup(self, punchline: str, episode_id: str) -> str:
        """Render high-resolution graphic apparel mockup with the punchline."""
        base_template_path = os.path.join(TEMPLATES_DIR, "tshirt_mockup_base.png")
        if not os.path.exists(base_template_path):
            return ""

        im = Image.open(base_template_path).convert("RGBA")
        draw = ImageDraw.Draw(im)

        # Print canvas area on shirt
        print_x = 400
        print_y = 390

        # Draw graphic distress / grunge box on shirt
        draw.rounded_rectangle([295, 290, 505, 490], radius=12, fill=(15, 15, 20), outline=(255, 60, 90), width=3)
        draw.rounded_rectangle([300, 295, 500, 485], radius=8, outline=(255, 255, 255, 60), width=1)

        # Bold distressed text styling
        font_title = get_font(26)
        font_sub = get_font(18)
        font_badge = get_font(14)

        # Top tag
        draw.text((330, 310), "CRASH OUT APPAREL", fill=(255, 45, 85), font=font_badge)

        # Word wrapping for punchline
        words = punchline.upper().split()
        line1 = " ".join(words[:2]) if len(words) >= 2 else punchline.upper()
        line2 = " ".join(words[2:4]) if len(words) >= 4 else (" ".join(words[2:]) if len(words) > 2 else "")
        line3 = " ".join(words[4:]) if len(words) > 4 else ""

        # Draw lines centered
        def draw_centered_text(text, y, color, font):
            if not text:
                return
            bbox = font.getbbox(text)
            text_w = bbox[2] - bbox[0]
            draw.text((400 - text_w // 2, y), text, fill=color, font=font)

        draw_centered_text(line1, 350, (255, 255, 255), font_title)
        if line2:
            draw_centered_text(line2, 385, (255, 225, 0), font_title)
        if line3:
            draw_centered_text(line3, 420, (255, 255, 255), font_title)

        draw_centered_text("OFFICIAL PEARSON FAMILY DROP", 460, (140, 150, 170), font_badge)

        # Prefer named episode folder from state when available.
        from app.state import state_manager

        ep = state_manager.episodes.get(episode_id)
        if ep is not None:
            folder = ensure_episode_output_folder(ep)
        else:
            folder = episode_id
            episode_dir(folder)
        rel = f"{folder}/merch_mockup.png"
        output_path = os.path.join(episode_dir(folder), "merch_mockup.png")
        im.save(output_path, "PNG")
        return public_url(rel)

    def prepare_deployment(self, episode_id: str, episode_title: str, merch_punchline: str) -> Dict[str, Any]:
        """Generate platform social metadata and Print-on-Demand payload."""
        mockup_url = self.generate_merch_mockup(merch_punchline, episode_id)

        # Social metadata
        social = {
            "youtube_shorts": {
                "title": f"{episode_title} #CrashOut #GenZ #Shorts",
                "description": (
                    f"Dad is having a full public meltdown. Watch the full animated episode!\n\n"
                    f"🛒 Official Limited Merch Drop ('{merch_punchline}'): https://crashout.shop/products/{episode_id}\n\n"
                    f"#CrashOut #Animation #SuburbanHumor #GenZSlang #TikTokHumor"
                ),
                "tags": ["crash out", "satirical animation", "family comedy", "suburban dad", "gen z humor"],
                "category_id": "23", # Comedy
                "scheduled_slot": "18:00 EST (Peak Gen-Z scroll window)"
            },
            "tiktok": {
                "caption": f"Dad is literally cooked on main 💀😭 '{merch_punchline}' hoodie drops tonight! link in bio #crashout #relatable #viral #dadsoftiktok #fyp",
                "sound_recommendation": "Original Sound - Crash Out Series (Trending Dialogue)",
                "content_disclosure": False
            },
            "instagram_reels": {
                "caption": f"When the receipt hits different 💳💥 Tap the link in bio to cop the official '{merch_punchline}' tee.\n.\n.\n#CrashOut #AnimatedSeries #AdultAnimation #RelatableComedy",
                "share_to_feed": True
            }
        }

        # Printify / Shopify E-Commerce Listing Payload
        merch_listing = {
            "product_title": f"The '{merch_punchline}' Heavyweight Boxy Tee",
            "retail_price_usd": 34.00,
            "cost_of_goods_usd": 12.50,
            "profit_margin_usd": 21.50,
            "product_type": "Apparel / Graphic T-Shirt",
            "mockup_preview_url": mockup_url,
            "variants": ["S", "M", "L", "XL", "2XL"],
            "print_provider": "Printify / Monster Digital (Direct-to-Garment)",
            "store_permalink": f"https://crashout.shop/products/{episode_id}"
        }

        return {
            "social": social,
            "merch": merch_listing,
            "mockup_url": mockup_url
        }

publisher_agent = Agent4Publisher()

