"""
weekly_briefing.py — Generates a weekly CEO briefing markdown document.

Can be:
  - Run directly: uv run python scheduler/weekly_briefing.py
  - Scheduled via Windows Task Scheduler (Mondays 08:45) or via the `schedule` library

Output: AI_Employee_Vault/Plans/CEO_Briefing_<YYYY-MM-DD>.md
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

VAULT_PATH = Path(os.getenv("VAULT_PATH", r"E:\ai_employee\AI_Employee_Vault"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-6"

try:
    import anthropic
except ImportError:
    print("anthropic not installed. Run: uv add anthropic", file=sys.stderr)
    sys.exit(1)

try:
    import schedule
except ImportError:
    print("schedule not installed. Run: uv add schedule", file=sys.stderr)
    sys.exit(1)

from agent.prompts import BRIEFING_PROMPT  # noqa: E402
from audit.logger import audit_logger  # noqa: E402


# ── Vault stats ───────────────────────────────────────────────────────────────

def _count_folder(folder: str) -> int:
    d = VAULT_PATH / folder
    if not d.exists():
        return 0
    return len(list(d.glob("*.md")))


def _gather_vault_stats() -> dict:
    return {
        "done": _count_folder("Done"),
        "approved": _count_folder("Approved"),
        "rejected": _count_folder("Rejected"),
        "pending_approvals": _count_folder("Pending_Approvals"),
        "needs_action": _count_folder("Needs_Action"),
    }


# ── Odoo P&L ─────────────────────────────────────────────────────────────────

def _get_pl_summary() -> str:
    try:
        from mcp_servers.odoo_mcp import get_accounting_report  # noqa: PLC0415
        result = get_accounting_report("last_week")
        if result.get("ok"):
            r = result["result"]
            return (
                f"Period: {r['date_from']} to {r['date_to']}\n"
                f"Total Income: ${r['total_income']:,.2f}\n"
                f"Total Expenses: ${r['total_expenses']:,.2f}\n"
                f"Net: ${r['net']:,.2f}"
            )
        return f"Odoo unavailable: {result.get('error', 'unknown error')}"
    except Exception as exc:
        return f"Odoo unavailable: {exc}"


# ── Audit summary ─────────────────────────────────────────────────────────────

def _summarise_audit(records: list[dict]) -> str:
    if not records:
        return "No audit records in the last 7 days."
    action_counts: dict[str, int] = {}
    for rec in records:
        action = rec.get("action", "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1
    lines = [f"- {action}: {count}" for action, count in sorted(action_counts.items(), key=lambda x: -x[1])]
    return "\n".join(lines)


# ── Briefing generation ───────────────────────────────────────────────────────

def generate_briefing() -> Path:
    print("[Briefing] Gathering data...")

    vault_stats = _gather_vault_stats()
    pl_summary = _get_pl_summary()
    audit_records = audit_logger.read_last_n_days(7)
    audit_summary = _summarise_audit(audit_records)

    today = date.today()
    context = f"""## Data for CEO Briefing — Week ending {today}

### Vault Task Counts
- Done this week: {vault_stats['done']}
- Approved: {vault_stats['approved']}
- Rejected: {vault_stats['rejected']}
- Pending Approvals (awaiting CEO): {vault_stats['pending_approvals']}
- Still in Needs_Action: {vault_stats['needs_action']}

### Financial Summary (Odoo)
{pl_summary}

### Agent Activity (last 7 days audit log)
{audit_summary}

Total audit events: {len(audit_records)}
"""

    print("[Briefing] Calling Claude for narrative generation...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=BRIEFING_PROMPT,
        messages=[{"role": "user", "content": context}],
    )
    narrative = response.content[0].text if response.content else "No content generated."

    # Write output
    plans_dir = VAULT_PATH / "Plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    out_path = plans_dir / f"CEO_Briefing_{today.isoformat()}.md"
    out_path.write_text(
        f"""---
type: ceo_briefing
date: {today.isoformat()}
generated: {datetime.now(timezone.utc).isoformat()}
---

{narrative}
""",
        encoding="utf-8",
    )
    print(f"[Briefing] Written to {out_path}")
    return out_path


# ── Scheduler entry point ─────────────────────────────────────────────────────

def _run_scheduled() -> None:
    try:
        generate_briefing()
    except Exception as exc:
        print(f"[Briefing] Error: {exc}", file=sys.stderr)


def start_scheduler() -> None:
    """Run as a persistent scheduler — generates briefing every Monday at 08:45."""
    import time  # noqa: PLC0415
    schedule.every().monday.at("08:45").do(_run_scheduled)
    print("[Briefing] Scheduler started. Next run: Monday 08:45.")
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="CEO Weekly Briefing Generator")
    parser.add_argument(
        "--now", action="store_true", help="Generate briefing immediately (skip scheduler)"
    )
    args = parser.parse_args()

    if args.now or len(sys.argv) == 1:
        # Default: run immediately (useful for Task Scheduler invocation or manual testing)
        generate_briefing()
    else:
        start_scheduler()
