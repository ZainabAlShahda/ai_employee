"""
twitter_watcher.py — polls X (Twitter) API v2 for mentions.
Primary: Tweepy Client.get_users_mentions()
Fallback: Playwright headed=False with saved session (twitter.com/notifications)

Writes TWITTER_<tweet_id>.md into Needs_Action/ when new items are detected.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
VAULT_PATH = Path(os.getenv("VAULT_PATH", r"E:\ai_employee\AI_Employee_Vault"))
NEEDS_ACTION = VAULT_PATH / "Needs_Action"
SEEN_FILE = Path(__file__).parent / "seen_twitter.json"
SESSION_FILE = Path(__file__).parent / "twitter_session.json"
POLL_INTERVAL = 60  # seconds


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(list(seen)))


def write_vault_item(tweet_id: str, author: str, text: str, created_at: str) -> None:
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    dest = NEEDS_ACTION / f"TWITTER_{tweet_id}.md"
    dest.write_text(
        f"""---
type: twitter_mention
id: {tweet_id}
author: {author}
created_at: {created_at}
---

{text}
""",
        encoding="utf-8",
    )
    print(f"[TW] New mention from @{author}: {text[:60]!r}")


# ── Primary: Tweepy API v2 ─────────────────────────────────────────────────────

def poll_via_tweepy(seen: set[str]) -> bool:
    """Returns True if successful, False if unavailable."""
    if not TWITTER_BEARER_TOKEN:
        return False
    try:
        import tweepy  # noqa: PLC0415
    except ImportError:
        print("[TW] tweepy not installed.", file=sys.stderr)
        return False

    try:
        client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
        # Look up our own user id
        me = client.get_me()
        if not me or not me.data:
            return False
        user_id = me.data.id

        since_id = max(seen, default=None) if seen else None
        resp = client.get_users_mentions(
            id=user_id,
            since_id=since_id,
            tweet_fields=["created_at", "author_id", "text"],
            expansions=["author_id"],
            user_fields=["username"],
            max_results=10,
        )
        if not resp or not resp.data:
            return True  # success but no new mentions

        users = {u.id: u.username for u in (resp.includes.get("users") or [])}
        for tweet in resp.data:
            tweet_id = str(tweet.id)
            if tweet_id in seen:
                continue
            author = users.get(tweet.author_id, str(tweet.author_id))
            created_at = str(tweet.created_at or "")
            write_vault_item(tweet_id, author, tweet.text, created_at)
            seen.add(tweet_id)

        return True
    except Exception as exc:
        print(f"[TW] Tweepy error: {exc}", file=sys.stderr)
        return False


# ── Fallback: Playwright ───────────────────────────────────────────────────────

def poll_via_playwright(seen: set[str]) -> None:
    """Headless Playwright scrape of twitter.com/notifications."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        print("[TW] playwright not installed.", file=sys.stderr)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx_kwargs: dict = {"viewport": {"width": 1280, "height": 800}}
        if SESSION_FILE.exists():
            ctx_kwargs["storage_state"] = str(SESSION_FILE)
        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()
        page.goto("https://twitter.com/notifications", wait_until="networkidle", timeout=30_000)

        # Save updated session
        context.storage_state(path=str(SESSION_FILE))

        # Extract tweet ids from notification links
        links = page.eval_on_selector_all(
            "a[href*='/status/']",
            "els => els.map(e => e.href)",
        )
        for link in links:
            try:
                tweet_id = link.split("/status/")[1].split("?")[0]
                if tweet_id in seen:
                    continue
                write_vault_item(tweet_id, "unknown", f"Mention detected via Playwright: {link}", "")
                seen.add(tweet_id)
            except IndexError:
                continue

        browser.close()


# ── Main ───────────────────────────────────────────────────────────────────────

def poll_once(seen: set[str]) -> None:
    if not poll_via_tweepy(seen):
        print("[TW] Falling back to Playwright.", file=sys.stderr)
        poll_via_playwright(seen)
    save_seen(seen)


def main() -> None:
    print("[TW] Twitter watcher started.")
    seen = load_seen()
    while True:
        try:
            poll_once(seen)
        except Exception as exc:
            print(f"[TW] Unhandled error: {exc}", file=sys.stderr)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
