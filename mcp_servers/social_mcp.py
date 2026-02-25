"""
social_mcp.py — MCP server exposing social media posting as tools.
Tools: post_linkedin, post_facebook, post_instagram, post_twitter

Run: uv run python mcp_servers/social_mcp.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PAGE_ID = os.getenv("META_PAGE_ID", "")
META_IG_ACCOUNT_ID = os.getenv("META_IG_ACCOUNT_ID", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
LINKEDIN_TOKEN = os.getenv("LINKEDIN_TOKEN", "")
LINKEDIN_PERSON_URN = os.getenv("LINKEDIN_PERSON_URN", "")

try:
    from fastmcp import FastMCP
except ImportError:
    print("fastmcp not installed. Run: uv add fastmcp", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP("social")


# ── LinkedIn ──────────────────────────────────────────────────────────────────

@mcp.tool()
def post_linkedin(text: str) -> dict:
    """Post a text update to LinkedIn via LinkedIn API v2 UGC posts."""
    try:
        if not LINKEDIN_TOKEN or not LINKEDIN_PERSON_URN:
            return {"ok": False, "error": "LINKEDIN_TOKEN or LINKEDIN_PERSON_URN not set"}
        headers = {
            "Authorization": f"Bearer {LINKEDIN_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        body = {
            "author": f"urn:li:person:{LINKEDIN_PERSON_URN}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        return {"ok": True, "result": f"LinkedIn post published: {resp.headers.get('x-restli-id', '')}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Facebook ──────────────────────────────────────────────────────────────────

@mcp.tool()
def post_facebook(text: str, image_url: str = "") -> dict:
    """Post a status update (optionally with image) to a Facebook Page."""
    try:
        if not META_ACCESS_TOKEN or not META_PAGE_ID:
            return {"ok": False, "error": "META_ACCESS_TOKEN or META_PAGE_ID not set"}
        url = f"https://graph.facebook.com/v19.0/{META_PAGE_ID}/feed"
        payload: dict = {"message": text, "access_token": META_ACCESS_TOKEN}
        if image_url:
            payload["link"] = image_url
        resp = requests.post(url, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {"ok": True, "result": {"post_id": data.get("id")}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Instagram ─────────────────────────────────────────────────────────────────

@mcp.tool()
def post_instagram(image_url: str, caption: str) -> dict:
    """
    Publish a photo to Instagram Business via Meta Graph API.
    Step 1: Create media container. Step 2: Publish container.
    """
    try:
        if not META_ACCESS_TOKEN or not META_IG_ACCOUNT_ID:
            return {"ok": False, "error": "META_ACCESS_TOKEN or META_IG_ACCOUNT_ID not set"}
        base = f"https://graph.facebook.com/v19.0/{META_IG_ACCOUNT_ID}"

        # Step 1: create container
        container_resp = requests.post(
            f"{base}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": META_ACCESS_TOKEN,
            },
            timeout=15,
        )
        container_resp.raise_for_status()
        creation_id = container_resp.json().get("id")
        if not creation_id:
            return {"ok": False, "error": "No container id returned"}

        # Step 2: wait briefly then publish
        time.sleep(2)
        publish_resp = requests.post(
            f"{base}/media_publish",
            params={"creation_id": creation_id, "access_token": META_ACCESS_TOKEN},
            timeout=15,
        )
        publish_resp.raise_for_status()
        media_id = publish_resp.json().get("id")
        return {"ok": True, "result": {"media_id": media_id}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Twitter / X ───────────────────────────────────────────────────────────────

@mcp.tool()
def post_twitter(text: str) -> dict:
    """Post a tweet via Twitter API v2 using Tweepy."""
    try:
        if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
            return {"ok": False, "error": "Twitter API credentials not fully set"}
        import tweepy  # noqa: PLC0415
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
        resp = client.create_tweet(text=text)
        tweet_id = resp.data.get("id") if resp.data else "unknown"
        return {"ok": True, "result": {"tweet_id": tweet_id}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    mcp.run()
