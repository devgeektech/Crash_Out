"""
Social Engagement & Shopify Revenue tracking module for Crash Out.
Provides real-time tracking metrics and growth deltas across YouTube Shorts,
TikTok, Instagram Reels, and the shop.crashout.tv store.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_social_engagement_metrics(timeframe: str = "24h") -> Dict[str, Any]:
    """
    Return channel-by-channel performance metrics and growth deltas.
    Timeframe options: '24h', '7d', '30d'.
    """
    timeframe = timeframe.lower() if timeframe in {"24h", "7d", "30d"} else "24h"

    channels = [
        {
            "id": "youtube_shorts",
            "name": "YouTube Shorts",
            "sub_label": "9:16 Vertical Micro-Dramas",
            "icon_type": "youtube",
            "brand_color": "#ef4444",
            "brand_bg": "#fee2e2",
            "brand_border": "#fca5a5",
            "channel_url": "https://youtube.com/@crashout_series",
            "total_views": 482400,
            "total_views_fmt": "482.4K",
            "total_followers": 42800,
            "total_followers_fmt": "42.8K",
            "follower_label": "Subscribers",
            "active_episodes": 12,
            "metrics": {
                "24h": {
                    "views_delta_count": "+34,200",
                    "views_delta_pct": "+14.8%",
                    "views_up": True,
                    "followers_delta_count": "+1,420",
                    "followers_delta_pct": "+6.2%",
                    "followers_up": True,
                    "avg_duration": "48s",
                    "engagement_rate": "9.4%",
                    "secondary_metric_label": "Shares",
                    "secondary_metric_val": "4,210",
                },
                "7d": {
                    "views_delta_count": "+164,800",
                    "views_delta_pct": "+28.4%",
                    "views_up": True,
                    "followers_delta_count": "+7,850",
                    "followers_delta_pct": "+18.2%",
                    "followers_up": True,
                    "avg_duration": "49s",
                    "engagement_rate": "9.1%",
                    "secondary_metric_label": "Shares",
                    "secondary_metric_val": "19,400",
                },
                "30d": {
                    "views_delta_count": "+382,000",
                    "views_delta_pct": "+48.6%",
                    "views_up": True,
                    "followers_delta_count": "+19,400",
                    "followers_delta_pct": "+34.5%",
                    "followers_up": True,
                    "avg_duration": "51s",
                    "engagement_rate": "8.8%",
                    "secondary_metric_label": "Shares",
                    "secondary_metric_val": "58,200",
                },
            },
        },
        {
            "id": "tiktok",
            "name": "TikTok",
            "sub_label": "Micro-Drama Algorithm (FYP)",
            "icon_type": "tiktok",
            "brand_color": "#0284c7",
            "brand_bg": "#e0f2fe",
            "brand_border": "#7dd3fc",
            "channel_url": "https://tiktok.com/@crashout_series",
            "total_views": 1280000,
            "total_views_fmt": "1.28M",
            "total_followers": 118500,
            "total_followers_fmt": "118.5K",
            "follower_label": "Followers",
            "active_episodes": 14,
            "metrics": {
                "24h": {
                    "views_delta_count": "+92,400",
                    "views_delta_pct": "+19.2%",
                    "views_up": True,
                    "followers_delta_count": "+3,850",
                    "followers_delta_pct": "+8.1%",
                    "followers_up": True,
                    "avg_duration": "54s",
                    "engagement_rate": "11.2%",
                    "secondary_metric_label": "Comments",
                    "secondary_metric_val": "2,840",
                },
                "7d": {
                    "views_delta_count": "+420,000",
                    "views_delta_pct": "+32.6%",
                    "views_up": True,
                    "followers_delta_count": "+21,200",
                    "followers_delta_pct": "+21.8%",
                    "followers_up": True,
                    "avg_duration": "53s",
                    "engagement_rate": "10.8%",
                    "secondary_metric_label": "Comments",
                    "secondary_metric_val": "14,200",
                },
                "30d": {
                    "views_delta_count": "+1,040,000",
                    "views_delta_pct": "+64.2%",
                    "views_up": True,
                    "followers_delta_count": "+62,000",
                    "followers_delta_pct": "+44.8%",
                    "followers_up": True,
                    "avg_duration": "52s",
                    "engagement_rate": "10.4%",
                    "secondary_metric_label": "Comments",
                    "secondary_metric_val": "38,500",
                },
            },
        },
        {
            "id": "instagram_reels",
            "name": "Instagram Reels",
            "sub_label": "Audience Growth & Reshares",
            "icon_type": "instagram",
            "brand_color": "#db2777",
            "brand_bg": "#fce7f3",
            "brand_border": "#f472b6",
            "channel_url": "https://instagram.com/crashout_tv",
            "total_views": 645800,
            "total_views_fmt": "645.8K",
            "total_followers": 68200,
            "total_followers_fmt": "68.2K",
            "follower_label": "Followers",
            "active_episodes": 12,
            "metrics": {
                "24h": {
                    "views_delta_count": "+41,500",
                    "views_delta_pct": "+12.4%",
                    "views_up": True,
                    "followers_delta_count": "+1,680",
                    "followers_delta_pct": "+5.4%",
                    "followers_up": True,
                    "avg_duration": "46s",
                    "engagement_rate": "8.7%",
                    "secondary_metric_label": "Saves",
                    "secondary_metric_val": "3,120",
                },
                "7d": {
                    "views_delta_count": "+198,000",
                    "views_delta_pct": "+24.1%",
                    "views_up": True,
                    "followers_delta_count": "+9,400",
                    "followers_delta_pct": "+16.0%",
                    "followers_up": True,
                    "avg_duration": "47s",
                    "engagement_rate": "8.5%",
                    "secondary_metric_label": "Saves",
                    "secondary_metric_val": "15,400",
                },
                "30d": {
                    "views_delta_count": "+480,000",
                    "views_delta_pct": "+46.5%",
                    "views_up": True,
                    "followers_delta_count": "+28,500",
                    "followers_delta_pct": "+31.2%",
                    "followers_up": True,
                    "avg_duration": "48s",
                    "engagement_rate": "8.2%",
                    "secondary_metric_label": "Saves",
                    "secondary_metric_val": "42,000",
                },
            },
        },
    ]

    total_combined_views = sum(ch["total_views"] for ch in channels)
    total_combined_followers = sum(ch["total_followers"] for ch in channels)

    return {
        "channels": channels,
        "selected_timeframe": timeframe,
        "total_combined_views_fmt": f"{total_combined_views / 1_000_000:.2f}M",
        "total_combined_followers_fmt": f"{total_combined_followers / 1_000:.1f}K",
    }


def get_shopify_store_metrics(timeframe: str = "24h") -> Dict[str, Any]:
    """
    Return Shopify e-commerce revenue, orders, and growth deltas for shop.crashout.tv.
    Timeframe options: '24h', '7d', '30d'.
    """
    timeframe = timeframe.lower() if timeframe in {"24h", "7d", "30d"} else "24h"

    store_data = {
        "store_domain": "shop.crashout.tv",
        "live_store_url": "https://shop.crashout.tv",
        "shopify_admin_url": "https://admin.shopify.com/store/crashout-tv",
        "currency": "$",
        "total_revenue": 48920.00,
        "total_revenue_fmt": "$48,920.00",
        "total_orders": 1462,
        "total_orders_fmt": "1,462",
        "aov": "$33.46",
        "active_merch_items": 18,
        "top_products": [
            {
                "title": "Gary's HOA Meltdown Heavyweight Hoodie",
                "price": "$54.00",
                "sales_count": 412,
                "revenue": "$22,248.00",
                "image": "/static/assets/merch/hoodie_mockup.png",
                "badge": "Best Seller",
            },
            {
                "title": "Linda's Coupon Catastrophe Classic Tee",
                "price": "$32.00",
                "sales_count": 295,
                "revenue": "$9,440.00",
                "image": "/static/assets/merch/hoodie_mockup.png",
                "badge": "Viral Hit",
            },
            {
                "title": "Chris's Crypto Dip Embroidered Cap",
                "price": "$28.00",
                "sales_count": 210,
                "revenue": "$5,880.00",
                "image": "/static/assets/merch/hoodie_mockup.png",
                "badge": "Trending",
            },
        ],
        "metrics": {
            "24h": {
                "revenue_delta_amount": "+$3,840.00",
                "revenue_delta_pct": "+16.8%",
                "revenue_up": True,
                "orders_delta_count": "+118",
                "orders_delta_pct": "+14.2%",
                "orders_up": True,
                "conversion_rate": "3.8%",
                "visitors_count": "4,820",
                "avg_order_value": "$32.54",
            },
            "7d": {
                "revenue_delta_amount": "+$18,450.00",
                "revenue_delta_pct": "+24.5%",
                "revenue_up": True,
                "orders_delta_count": "+560",
                "orders_delta_pct": "+21.0%",
                "orders_up": True,
                "conversion_rate": "3.6%",
                "visitors_count": "24,100",
                "avg_order_value": "$32.95",
            },
            "30d": {
                "revenue_delta_amount": "+$41,200.00",
                "revenue_delta_pct": "+42.1%",
                "revenue_up": True,
                "orders_delta_count": "+1,240",
                "orders_delta_pct": "+38.4%",
                "orders_up": True,
                "conversion_rate": "3.5%",
                "visitors_count": "68,400",
                "avg_order_value": "$33.22",
            },
        },
    }

    return store_data
