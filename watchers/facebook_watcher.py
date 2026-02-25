"""
facebook_watcher.py — polls Meta Graph API for page posts and mentions.
Writes FACEBOOK_<post_id>.md into Needs_Action/ when new items are detected.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PAGE_ID = os.getenv("META_PAGE_ID", "")
VAULT_PATH = Path(os.getenv("VAULT_PATH", r"E:\ai_employee\AI_Employee_Vault"))
NEEDS_ACTION = VAULT_PATH / "Needs_Action"
SEEN_FILE = Path(__file__).parent / "seen_fb.json"
POLL_INTERVAL = 60  # seconds


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(list(seen)))


def graph_get(path: str, params: dict | None = None) -> dict:
    """Make a Meta Graph API GET request with exponential backoff."""
    url = f"https://graph.facebook.com/v19.0/{path}"
    p = {"access_token": META_ACCESS_TOKEN, **(params or {})}
    delay = 1
    for attempt in range(5):
        try:
            resp = requests.get(url, params=p, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            print(f"[FB] API error (attempt {attempt+1}): {exc}", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    return {}


def write_vault_item(post_id: str, from_name: str, message: str, created_time: str) -> None:
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    dest = NEEDS_ACTION / f"FACEBOOK_{post_id}.md"
    dest.write_text(
        f"""---
type: facebook_post
id: {post_id}
from: {from_name}
created_time: {created_time}
---

{message}
""",
        encoding="utf-8",
    )
    print(f"[FB] New post from {from_name}: {message[:60]!r}")


def poll_once(seen: set[str]) -> None:
    if not META_ACCESS_TOKEN or not META_PAGE_ID:
        print("[FB] META_ACCESS_TOKEN or META_PAGE_ID not set — skipping.", file=sys.stderr)
        return

    # Poll page feed
    data = graph_get(f"{META_PAGE_ID}/feed", {"fields": "id,from,message,created_time"})
    for item in data.get("data", []):
        post_id = item.get("id", "")
        if not post_id or post_id in seen:
            continue
        from_name = item.get("from", {}).get("name", "Unknown")
        message = item.get("message", "")
        created_time = item.get("created_time", "")
        write_vault_item(post_id, from_name, message, created_time)
        seen.add(post_id)

    # Poll mentions
    mentions = graph_get(f"{META_PAGE_ID}/mentions", {"fields": "id,from,message,created_time"})
    for item in mentions.get("data", []):
        post_id = item.get("id", "")
        if not post_id or post_id in seen:
            continue
        from_name = item.get("from", {}).get("name", "Unknown")
        message = item.get("message", "")
        created_time = item.get("created_time", "")
        write_vault_item(post_id, from_name, message, created_time)
        seen.add(post_id)

    save_seen(seen)


def main() -> None:
    print("[FB] Facebook watcher started.")
    seen = load_seen()
    while True:
        try:
            poll_once(seen)
        except Exception as exc:
            print(f"[FB] Unhandled error: {exc}", file=sys.stderr)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
