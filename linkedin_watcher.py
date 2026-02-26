from playwright.sync_api import sync_playwright
from pathlib import Path
import time

def watch_linkedin(vault_path):
    needs_action = Path(vault_path) / 'Needs_Action'
    needs_action.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.linkedin.com/login")
        print("[LinkedIn] Please log in manually...")

        # Wait for login
        page.wait_for_load_state("networkidle")

        while True:
            # Go to notifications page
            page.goto("https://www.linkedin.com/notifications/")
            page.wait_for_load_state("networkidle")

            # Scrape notification items
            notifications = page.query_selector_all("div.feed-notification-card__message")
            for idx, notif in enumerate(notifications[:5]):  # limit to 5 latest
                text = notif.inner_text().strip()
                meta_path = needs_action / f"LINKEDIN_{idx}.md"
                if not meta_path.exists():
                    meta_path.write_text(f"""---
type: linkedin_notification
source: LinkedIn
---

{text}
""")
                    print(f"[LinkedIn] New notification: {text[:60]}...")

            time.sleep(60)  # check every minute

if __name__ == "__main__":
    vault_path = r"E:\ai_employee\AI_Employee_Vault"
    watch_linkedin(vault_path)
