"""
gmail_mcp.py — MCP server exposing Gmail write actions as tools.
Tools: send_email, reply_email, label_email

Run: uv run python mcp_servers/gmail_mcp.py
"""

from __future__ import annotations

import base64
import os
import sys
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Add project root to path so imports work from any cwd
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]
TOKEN_PATH = Path(__file__).parent.parent / "token.json"
CREDS_PATH = Path(__file__).parent.parent / "credentials.json"


def _get_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


# ── MCP Server ────────────────────────────────────────────────────────────────

try:
    from fastmcp import FastMCP  # noqa: E402
except ImportError:
    print("fastmcp not installed. Run: uv add fastmcp", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP("gmail")


@mcp.tool()
def send_email(to: str, subject: str, body: str) -> dict:
    """Send a new email via Gmail API."""
    try:
        service = _get_service()
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"ok": True, "result": f"Email sent to {to}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def reply_email(message_id: str, body: str) -> dict:
    """Reply to an existing email thread."""
    try:
        service = _get_service()
        # Fetch original to get thread id and headers
        original = service.users().messages().get(
            userId="me", id=message_id, format="metadata",
            metadataHeaders=["Subject", "From", "To", "Message-ID"],
        ).execute()
        headers = {h["name"]: h["value"] for h in original["payload"]["headers"]}
        subject = headers.get("Subject", "Re:")
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"
        to = headers.get("From", "")
        thread_id = original["threadId"]
        in_reply_to = headers.get("Message-ID", "")

        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId="me", body={"raw": raw, "threadId": thread_id}
        ).execute()
        return {"ok": True, "result": f"Reply sent in thread {thread_id}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def label_email(message_id: str, label: str) -> dict:
    """Apply a label to an email (e.g. 'INBOX', 'STARRED', or a custom label name)."""
    try:
        service = _get_service()
        # Try to find label id by name
        labels_resp = service.users().labels().list(userId="me").execute()
        label_id = None
        for lbl in labels_resp.get("labels", []):
            if lbl["name"].lower() == label.lower():
                label_id = lbl["id"]
                break
        if not label_id:
            # Create label
            new_label = service.users().labels().create(
                userId="me", body={"name": label}
            ).execute()
            label_id = new_label["id"]
        service.users().messages().modify(
            userId="me", id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()
        return {"ok": True, "result": f"Label '{label}' applied to {message_id}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    mcp.run()
