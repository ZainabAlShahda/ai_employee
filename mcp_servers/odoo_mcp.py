"""
odoo_mcp.py — MCP server exposing Odoo Community JSON-RPC actions as tools.
Tools: create_invoice, list_contacts, get_accounting_report, post_payment

Run: uv run python mcp_servers/odoo_mcp.py

Requires Odoo 19 Community at ODOO_URL with a database set in ODOO_DB.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")

try:
    from fastmcp import FastMCP
except ImportError:
    print("fastmcp not installed. Run: uv add fastmcp", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP("odoo")

# ── Odoo JSON-RPC helpers ─────────────────────────────────────────────────────

_uid_cache: int | None = None


def _authenticate() -> int:
    global _uid_cache
    if _uid_cache:
        return _uid_cache
    resp = requests.post(
        f"{ODOO_URL}/web/session/authenticate",
        json={
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": ODOO_DB,
                "login": ODOO_USERNAME,
                "password": ODOO_PASSWORD,
            },
        },
        timeout=15,
    )
    resp.raise_for_status()
    result = resp.json().get("result", {})
    uid = result.get("uid")
    if not uid:
        raise RuntimeError(f"Odoo authentication failed: {resp.text}")
    _uid_cache = uid
    return uid


def _call_kw(model: str, method: str, args: list, kwargs: dict | None = None) -> object:
    uid = _authenticate()
    resp = requests.post(
        f"{ODOO_URL}/web/dataset/call_kw",
        json={
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": method,
                "args": args,
                "kwargs": kwargs or {},
                "uid": uid,
                "password": ODOO_PASSWORD,
                "db": ODOO_DB,
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("data", {}).get("message", str(data["error"])))
    return data.get("result")


# ── MCP Tools ─────────────────────────────────────────────────────────────────


@mcp.tool()
def create_invoice(partner_name: str, amount: float, description: str) -> dict:
    """Create a customer invoice in Odoo for the given partner and amount."""
    try:
        # Find or create partner
        partners = _call_kw(
            "res.partner", "search_read",
            [[["name", "ilike", partner_name]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if partners:
            partner_id = partners[0]["id"]
        else:
            partner_id = _call_kw(
                "res.partner", "create",
                [{"name": partner_name}],
            )

        # Create invoice
        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": partner_id,
            "invoice_line_ids": [
                (0, 0, {
                    "name": description,
                    "quantity": 1,
                    "price_unit": amount,
                })
            ],
        }
        invoice_id = _call_kw("account.move", "create", [invoice_vals])
        return {"ok": True, "result": {"invoice_id": invoice_id, "partner": partner_name, "amount": amount}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def list_contacts(query: str) -> dict:
    """Search Odoo contacts (res.partner) by name."""
    try:
        partners = _call_kw(
            "res.partner", "search_read",
            [[["name", "ilike", query]]],
            {"fields": ["id", "name", "email", "phone"], "limit": 20},
        )
        return {"ok": True, "result": partners}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def get_accounting_report(period: str) -> dict:
    """
    Return a P&L summary for the given period.
    period: 'last_week' | 'last_month' | 'this_year'
    """
    try:
        from datetime import date, timedelta  # noqa: PLC0415

        today = date.today()
        if period == "last_week":
            date_from = today - timedelta(days=7)
        elif period == "last_month":
            date_from = today.replace(day=1) - timedelta(days=1)
            date_from = date_from.replace(day=1)
        else:  # this_year
            date_from = today.replace(month=1, day=1)

        # Read account.move.line for income/expense
        lines = _call_kw(
            "account.move.line", "search_read",
            [[
                ["date", ">=", str(date_from)],
                ["date", "<=", str(today)],
                ["move_id.state", "=", "posted"],
            ]],
            {"fields": ["name", "debit", "credit", "account_id", "date"], "limit": 500},
        )
        total_debit = sum(l["debit"] for l in lines)  # type: ignore[index]
        total_credit = sum(l["credit"] for l in lines)  # type: ignore[index]
        return {
            "ok": True,
            "result": {
                "period": period,
                "date_from": str(date_from),
                "date_to": str(today),
                "total_income": total_credit,
                "total_expenses": total_debit,
                "net": total_credit - total_debit,
                "lines_count": len(lines),  # type: ignore[arg-type]
            },
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def post_payment(invoice_id: int, amount: float) -> dict:
    """Register a payment against an Odoo invoice."""
    try:
        # Use account.payment.register wizard
        wizard_id = _call_kw(
            "account.payment.register", "create",
            [{
                "amount": amount,
                "active_ids": [invoice_id],
                "active_model": "account.move",
            }],
        )
        _call_kw(
            "account.payment.register", "action_create_payments",
            [[wizard_id]],
        )
        return {"ok": True, "result": f"Payment of {amount} registered for invoice {invoice_id}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    mcp.run()
