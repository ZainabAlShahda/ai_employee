from playwright.sync_api import sync_playwright
from pathlib import Path
import time

def watch_whatsapp(vault_path):
    needs_action = Path(vault_path) / 'Needs_Action'
    needs_action.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://web.whatsapp.com")
        print("[WhatsApp] Scan QR code to log in...")

        while True:
            # Example: scrape unread chats
            unread_chats = page.query_selector_all("span[aria-label='Unread message']")
            for chat in unread_chats:
                chat_name = chat.inner_text()
                meta_path = needs_action / f"WHATSAPP_{chat_name}.md"
                if not meta_path.exists():
                    meta_path.write_text(f"""---
type: whatsapp_chat
name: {chat_name}
---

New WhatsApp chat detected.
""")