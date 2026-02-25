"""
ralph_loop.py — Claude API reasoning loop (the "Ralph Wiggum" loop).

Reads a task .md file from Needs_Action/, moves it to In_Progress/, iterates
Claude tool-use turns until done or max turns reached, then writes a Plan.md
and moves the task to Done/.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

VAULT_PATH = Path(os.getenv("VAULT_PATH", r"E:\ai_employee\AI_Employee_Vault"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MAX_TURNS = 10
MODEL = "claude-opus-4-6"

try:
    import anthropic
except ImportError:
    print("anthropic not installed. Run: uv add anthropic", file=sys.stderr)
    sys.exit(1)

from agent.prompts import SYSTEM_PROMPT  # noqa: E402
from agent.skills import TOOL_SCHEMAS, call_skill  # noqa: E402
from audit.logger import audit_logger  # noqa: E402


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _move(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    src.rename(dest)
    return dest


def _build_tool_result(tool_use_id: str, result: dict) -> dict:
    import json  # noqa: PLC0415
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": json.dumps(result),
    }


def run(task_path: Path) -> None:
    """
    Run the Ralph loop for a single task file.
    Raises on unrecoverable errors (orchestrator handles retry logic).
    """
    task_name = task_path.name
    print(f"[Ralph] Starting task: {task_name}")

    # ── Read task content ──────────────────────────────────────────────────
    task_content = task_path.read_text(encoding="utf-8")

    # ── Claim: move to In_Progress ─────────────────────────────────────────
    in_progress_dir = VAULT_PATH / "In_Progress"
    task_path = _move(task_path, in_progress_dir)

    # ── Safety gate: payment > $500 check (pre-scan) ───────────────────────
    # Claude's system prompt enforces this; belt-and-suspenders pre-scan is
    # done inside call_skill for post_payment calls.

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    messages: list[dict] = [
        {
            "role": "user",
            "content": f"Task file: {task_name}\n\n{task_content}",
        }
    ]

    completed = False
    plan_written = False

    for turn in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Append assistant response to messages
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            completed = True
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                # ── Payment safety gate ──────────────────────────────────
                if tool_name == "post_payment":
                    amount = float(tool_input.get("amount", 0))
                    if amount > 500:
                        result = call_skill(
                            "request_approval",
                            {
                                "name": f"PAYMENT_APPROVAL_{task_name.replace('.md', '')}",
                                "details": (
                                    f"Payment of ${amount:.2f} requested for invoice "
                                    f"{tool_input.get('invoice_id')}.\n"
                                    f"Original task: {task_name}\n\n"
                                    "This exceeds the $500 autonomous limit. "
                                    "Please review and approve or reject."
                                ),
                            },
                        )
                        audit_logger.log(task_name, "request_approval", tool_input, result, turn)
                        tool_results.append(_build_tool_result(block.id, result))
                        completed = True  # halt after approval request
                        break

                result = call_skill(tool_name, tool_input)
                audit_logger.log(task_name, tool_name, tool_input, result, turn)
                tool_results.append(_build_tool_result(block.id, result))

                # If approval was requested, stop the loop
                if tool_name == "request_approval" and result.get("ok"):
                    completed = True

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            if completed:
                break
        else:
            # Unexpected stop reason
            break

    # ── Write plan if not already done by Claude ───────────────────────────
    plans_dir = VAULT_PATH / "Plans"
    plan_name = task_name.replace(".md", "_Plan.md")
    plan_dest = plans_dir / plan_name
    if not plan_dest.exists():
        plans_dir.mkdir(parents=True, exist_ok=True)
        # Extract text blocks from last assistant message
        last_content = messages[-1].get("content", []) if messages else []
        summary_parts = [b.text for b in last_content if hasattr(b, "text")] if isinstance(last_content, list) else []
        summary = "\n\n".join(summary_parts) or "Task processed by Ralph loop."
        plan_dest.write_text(
            f"""---
type: plan
task: {task_name}
created: {_ts()}
turns: {turn + 1}
---

# Plan: {task_name}

{summary}
""",
            encoding="utf-8",
        )
        plan_written = True

    # ── Move task to Done or Pending_Approvals ─────────────────────────────
    if not completed and turn + 1 >= MAX_TURNS:
        # Max turns exceeded — request human review
        call_skill(
            "request_approval",
            {
                "name": f"MAX_TURNS_{task_name.replace('.md', '')}",
                "details": (
                    f"Task {task_name} exceeded {MAX_TURNS} turns without completing.\n"
                    "Partial work may have been done. Please review and re-assign or close."
                ),
            },
        )
        _move(task_path, VAULT_PATH / "Pending_Approvals")
    else:
        done_dir = VAULT_PATH / "Done"
        _move(task_path, done_dir)

    audit_logger.log_completion(task_name, turns=turn + 1, plan_written=plan_written)
    print(f"[Ralph] Finished task: {task_name} (turns={turn + 1})")
