from __future__ import print_function
import os.path
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scope: read-only Gmail access
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_service():
    """Authenticate and return Gmail API service."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def watch_inbox(vault_path):
    """Poll Gmail inbox and drop new messages into Needs_Action folder."""
    service = get_service()
    needs_action = Path(vault_path) / 'Needs_Action'
    needs_action.mkdir(parents=True, exist_ok=True)

    seen_ids = set()

    while True:
        results = service.users().messages().list(userId='me', maxResults=5).execute()
        messages = results.get('messages', [])
        for msg in messages:
            msg_id = msg['id']
            if msg_id in seen_ids:
                continue
            msg_data = service.users().messages().get(userId='me', id=msg_id).execute()
            headers = msg_data['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')

            meta_path = needs_action / f"GMAIL_{msg_id}.md"
            meta_path.write_text(f"""---
type: gmail_message
id: {msg_id}
subject: {subject}
from: {sender}
---

New Gmail message detected.
""")
            print(f"[Gmail] New message: {subject} from {sender}")
            seen_ids.add(msg_id)

        time.sleep(30)  # check every 30 seconds

if __name__ == "__main__":
    vault_path = r"E:\ai_employee\AI_Employee_Vault"
    watch_inbox(vault_path)

