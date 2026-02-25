"""
skills.py — Skill registry mapping tool names → Python callables.

Each skill wraps the underlying MCP tool function and returns a uniform dict:
    {"ok": True, "result": ...}  or  {"ok": False, "error": "..."}
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

VAULT_PATH = Path(os.getenv("VAULT_PATH", r"E:\ai_employee\AI_Employee_Vault"))

# ── Lazy imports to avoid startup errors when creds are missing ───────────────

def _gmail():
    from mcp_servers.gmail_mcp import send_email, reply_email, label_email  # noqa: PLC0415
    return send_email, reply_email, label_email


def _social():
    from mcp_servers.social_mcp import (  # noqa: PLC0415
        post_linkedin, post_facebook, post_instagram, post_twitter,
    )
    return post_linkedin, post_facebook, post_instagram, post_twitter


def _odoo():
    from mcp_servers.odoo_mcp import (  # noqa: PLC0415
        create_invoice, list_contacts, get_accounting_report, post_payment,
    )
    return create_invoice, list_contacts, get_accounting_report, post_payment


# ── Vault helpers (no external API) ──────────────────────────────────────────

def write_plan(name: str, content: str) -> dict:
    """Write a Plan.md file to AI_Employee_Vault/Plans/."""
    try:
        plans_dir = VAULT_PATH / "Plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        dest = plans_dir / f"{name}.md"
        dest.write_text(content, encoding="utf-8")
        return {"ok": True, "result": f"Plan written to Plans/{name}.md"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def request_approval(name: str, details: str) -> dict:
    """Write a Pending_Approvals item to halt and await human sign-off."""
    try:
        pending_dir = VAULT_PATH / "Pending_Approvals"
        pending_dir.mkdir(parents=True, exist_ok=True)
        dest = pending_dir / f"{name}.md"
        dest.write_text(
            f"""---
type: approval_request
status: pending
---

{details}
""",
            encoding="utf-8",
        )
        return {"ok": True, "result": f"Approval requested: Pending_Approvals/{name}.md"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Skill wrappers ────────────────────────────────────────────────────────────

def _wrap(fn, *args, **kwargs) -> dict:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def skill_send_email(to: str, subject: str, body: str) -> dict:
    se, _, _ = _gmail()
    return _wrap(se, to=to, subject=subject, body=body)


def skill_reply_email(message_id: str, body: str) -> dict:
    _, re_, _ = _gmail()
    return _wrap(re_, message_id=message_id, body=body)


def skill_label_email(message_id: str, label: str) -> dict:
    _, _, le = _gmail()
    return _wrap(le, message_id=message_id, label=label)


def skill_post_linkedin(text: str) -> dict:
    pl, _, _, _ = _social()
    return _wrap(pl, text=text)


def skill_post_facebook(text: str, image_url: str = "") -> dict:
    _, pf, _, _ = _social()
    return _wrap(pf, text=text, image_url=image_url)


def skill_post_instagram(image_url: str, caption: str) -> dict:
    _, _, pi, _ = _social()
    return _wrap(pi, image_url=image_url, caption=caption)


def skill_post_twitter(text: str) -> dict:
    _, _, _, pt = _social()
    return _wrap(pt, text=text)


def skill_create_invoice(partner_name: str, amount: float, description: str) -> dict:
    ci, _, _, _ = _odoo()
    return _wrap(ci, partner_name=partner_name, amount=amount, description=description)


def skill_list_contacts(query: str) -> dict:
    _, lc, _, _ = _odoo()
    return _wrap(lc, query=query)


def skill_get_accounting_report(period: str) -> dict:
    _, _, gar, _ = _odoo()
    return _wrap(gar, period=period)


def skill_post_payment(invoice_id: int, amount: float) -> dict:
    _, _, _, pp = _odoo()
    return _wrap(pp, invoice_id=invoice_id, amount=amount)


# ── Registry ──────────────────────────────────────────────────────────────────

SKILL_REGISTRY: dict[str, callable] = {
    "send_email": skill_send_email,
    "reply_email": skill_reply_email,
    "label_email": skill_label_email,
    "post_linkedin": skill_post_linkedin,
    "post_facebook": skill_post_facebook,
    "post_instagram": skill_post_instagram,
    "post_twitter": skill_post_twitter,
    "create_invoice": skill_create_invoice,
    "list_contacts": skill_list_contacts,
    "get_accounting_report": skill_get_accounting_report,
    "post_payment": skill_post_payment,
    "write_plan": write_plan,
    "request_approval": request_approval,
}


# ── Anthropic tool schemas (for Claude API tool_use) ─────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "send_email",
        "description": "Send a new email via Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Plain-text email body"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "reply_email",
        "description": "Reply to an existing email thread.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Gmail message ID to reply to"},
                "body": {"type": "string", "description": "Reply body text"},
            },
            "required": ["message_id", "body"],
        },
    },
    {
        "name": "label_email",
        "description": "Apply a Gmail label to a message.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "label": {"type": "string", "description": "Label name (e.g. 'DONE', 'STARRED')"},
            },
            "required": ["message_id", "label"],
        },
    },
    {
        "name": "post_linkedin",
        "description": "Publish a text post to LinkedIn.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "post_facebook",
        "description": "Publish a post to the Facebook Page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "image_url": {"type": "string", "description": "Optional image URL"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "post_instagram",
        "description": "Publish a photo to Instagram Business.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string"},
                "caption": {"type": "string"},
            },
            "required": ["image_url", "caption"],
        },
    },
    {
        "name": "post_twitter",
        "description": "Publish a tweet via X API v2.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Tweet text (max 280 chars)"}},
            "required": ["text"],
        },
    },
    {
        "name": "create_invoice",
        "description": "Create a customer invoice in Odoo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "partner_name": {"type": "string"},
                "amount": {"type": "number"},
                "description": {"type": "string"},
            },
            "required": ["partner_name", "amount", "description"],
        },
    },
    {
        "name": "list_contacts",
        "description": "Search Odoo contacts by name.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_accounting_report",
        "description": "Get a P&L summary from Odoo. period: last_week | last_month | this_year",
        "input_schema": {
            "type": "object",
            "properties": {"period": {"type": "string", "enum": ["last_week", "last_month", "this_year"]}},
            "required": ["period"],
        },
    },
    {
        "name": "post_payment",
        "description": "Register a payment against an Odoo invoice. Blocked by system if amount > $500.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer"},
                "amount": {"type": "number"},
            },
            "required": ["invoice_id", "amount"],
        },
    },
    {
        "name": "write_plan",
        "description": "Write a Plan.md file summarising what was done.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "File name without extension"},
                "content": {"type": "string", "description": "Markdown content"},
            },
            "required": ["name", "content"],
        },
    },
    {
        "name": "request_approval",
        "description": "Write a Pending_Approvals item and stop. Use when action exceeds authority.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Approval item file name"},
                "details": {"type": "string", "description": "Full markdown details for human reviewer"},
            },
            "required": ["name", "details"],
        },
    },
]


def call_skill(name: str, inputs: dict) -> dict:
    """
    Dispatch a tool call to the registered skill function.

    In cloud mode, SEND_TOOLS are blocked at this layer as a safety net
    (ralph_loop's draft-only gate should have caught them first).
    """
    try:
        from platform.capabilities import DRAFT_ONLY_MODE, SEND_TOOLS  # noqa: PLC0415
        if DRAFT_ONLY_MODE and name in SEND_TOOLS:
            return {
                "ok": False,
                "error": (
                    f"Skill '{name}' is blocked in cloud (draft-only) mode. "
                    "Use request_approval to route this action to Local."
                ),
            }
    except ImportError:
        pass  # platform package not yet available — allow (Gold Tier compat)

    fn = SKILL_REGISTRY.get(name)
    if not fn:
        return {"ok": False, "error": f"Unknown skill: {name}"}
    try:
        return fn(**inputs)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
