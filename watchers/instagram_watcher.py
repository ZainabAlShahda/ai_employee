"""
instagram_watcher.py — polls Meta Graph API for Instagram business media and mentions.
Writes INSTAGRAM_<media_id>.md into Needs_Action/ when new items are detected.
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
META_IG_ACCOUNT_ID = os.getenv("META_IG_ACCOUNT_ID", "")
VAULT_PATH = Path(os.getenv("VAULT_PATH", r"E:\ai_employee\AI_Employee_Vault"))
NEEDS_ACTION = VAULT_PATH / "Needs_Action"
SEEN_FILE = Path(__file__).parent / "seen_ig.json"
POLL_INTERVAL = 60  # seconds


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(list(seen)))


def graph_get(path: str, params: dict | None = None) -> dict:
    url = f"https://graph.facebook.com/v19.0/{path}"
    p = {"access_token": META_ACCESS_TOKEN, **(params or {})}
    delay = 1
    for attempt in range(5):
        try:
            resp = requests.get(url, params=p, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            print(f"[IG] API error (attempt {attempt+1}): {exc}", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    return {}


def write_vault_item(media_id: str, username: str, caption: str, timestamp: str) -> None:
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    dest = NEEDS_ACTION / f"INSTAGRAM_{media_id}.md"
    dest.write_text(
        f"""---
type: instagram_mention
id: {media_id}
username: {username}
timestamp: {timestamp}
---

{caption}
""",
        encoding="utf-8",
    )
    print(f"[IG] New item from @{username}: {caption[:60]!r}")


def poll_once(seen: set[str]) -> None:
    if not META_ACCESS_TOKEN or not META_IG_ACCOUNT_ID:
        print("[IG] META_ACCESS_TOKEN or META_IG_ACCOUNT_ID not set — skipping.", file=sys.stderr)
        return

    # Poll recent media
    media = graph_get(
        f"{META_IG_ACCOUNT_ID}/media",
        {"fields": "id,username,caption,timestamp"},
    )
    for item in media.get("data", []):
        media_id = item.get("id", "")
        if not media_id or media_id in seen:
            continue
        username = item.get("username", "Unknown")
        caption = item.get("caption", "")
        timestamp = item.get("timestamp", "")
        write_vault_item(media_id, username, caption, timestamp)
        seen.add(media_id)

    # Poll @mentions via tagged media
    mentions = graph_get(
        f"{META_IG_ACCOUNT_ID}/tags",
        {"fields": "id,username,caption,timestamp"},
    )
    for item in mentions.get("data", []):
        media_id = item.get("id", "")
        if not media_id or media_id in seen:
            continue
        username = item.get("username", "Unknown")
        caption = item.get("caption", "")
        timestamp = item.get("timestamp", "")
        write_vault_item(media_id, username, caption, timestamp)
        seen.add(media_id)

    save_seen(seen)


def main() -> None:
    print("[IG] Instagram watcher started.")
    seen = load_seen()
    while True:
        try:
            poll_once(seen)
        except Exception as exc:
            print(f"[IG] Unhandled error: {exc}", file=sys.stderr)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
