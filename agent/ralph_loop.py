"""
ralph_loop.py — Claude API reasoning loop (the "Ralph Wiggum" loop).

Reads a task .md file from Needs_Action/ (or a domain subfolder), moves it to
In_Progress/<agent_id>/, iterates Claude tool-use turns until done or max turns
reached, then writes a Plan.md and moves the task to Done/.

Platinum Tier changes:
- Claims to In_Progress/<agent_id>/ (not flat In_Progress/)
- Draft-only gate: Cloud mode intercepts SEND_TOOLS and routes them through
  request_approval, writing a SEND_APPROVAL_* file to Pending_Approvals/
  for Local to execute.
- Tool schemas filtered by agent mode (cloud sees only CLOUD_SKILLS)
- System prompt switches to CLOUD_SYSTEM_PROMPT in cloud mode
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from agent_platform.config import agent_config  # noqa: E402
from agent_platform.capabilities import (  # noqa: E402
    DRAFT_ONLY_MODE,
    SEND_TOOLS,
    get_tool_schemas,
)

VAULT_PATH = agent_config.vault_path
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MAX_TURNS = 10
MODEL = "claude-opus-4-6"

try:
    import anthropic
except ImportError:
    print("anthropic not installed. Run: uv add anthropic", file=sys.stderr)
    sys.exit(1)

from agent.prompts import SYSTEM_PROMPT, CLOUD_SYSTEM_PROMPT  # noqa: E402
from agent.skills import call_skill  # noqa: E402
from audit.logger import audit_logger  # noqa: E402

_ACTIVE_PROMPT = CLOUD_SYSTEM_PROMPT if DRAFT_ONLY_MODE else SYSTEM_PROMPT


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _move(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    src.rename(dest)
    return dest


def _build_tool_result(tool_use_id: str, result: dict) -> dict:
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
    print(f"[Ralph] Starting task: {task_name} (mode={agent_config.mode})")

    # ── Read task content ──────────────────────────────────────────────────
    task_content = task_path.read_text(encoding="utf-8")

    # ── Claim: move to In_Progress/<agent_id>/ ────────────────────────────
    in_progress_dir = VAULT_PATH / "In_Progress" / agent_config.agent_id
    task_path = _move(task_path, in_progress_dir)

    # ── Special handling: Local processing a SEND_APPROVAL_* item ─────────
    # When Local picks up a SEND_APPROVAL file from Approved/, the content
    # contains the original tool name and inputs embedded in YAML frontmatter.
    # We parse and execute it directly without a Claude turn.
    if task_name.startswith("SEND_APPROVAL_") and agent_config.mode == "local":
        _execute_send_approval(task_path, task_name, task_content)
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    tool_schemas = get_tool_schemas()

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
            system=_ACTIVE_PROMPT,
            tools=tool_schemas,
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
                        completed = True
                        break

                # ── Cloud draft-only gate ────────────────────────────────
                if DRAFT_ONLY_MODE and tool_name in SEND_TOOLS:
                    approval_name = (
                        f"SEND_APPROVAL_{task_name.replace('.md', '')}_{tool_name}"
                    )
                    details = (
                        f"Cloud agent drafted action — Local must execute:\n\n"
                        f"**Tool:** `{tool_name}`\n\n"
                        f"**Inputs:**\n```json\n{json.dumps(tool_input, indent=2)}\n```\n\n"
                        f"**Original task:** {task_name}\n\n"
                        f"---\n\n"
                        f"<!-- platinum:tool:{tool_name} -->\n"
                        f"<!-- platinum:inputs:{json.dumps(tool_input)} -->\n"
                    )
                    result = call_skill("request_approval", {"name": approval_name, "details": details})
                    audit_logger.log(task_name, f"cloud_draft_{tool_name}", tool_input, result, turn)
                    tool_results.append(_build_tool_result(block.id, result))
                    completed = True
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
            break

    # ── Write plan if not already done by Claude ───────────────────────────
    plans_dir = VAULT_PATH / "Plans"
    plan_name = task_name.replace(".md", "_Plan.md")
    plan_dest = plans_dir / plan_name
    if not plan_dest.exists():
        plans_dir.mkdir(parents=True, exist_ok=True)
        last_content = messages[-1].get("content", []) if messages else []
        summary_parts = (
            [b.text for b in last_content if hasattr(b, "text")]
            if isinstance(last_content, list)
            else []
        )
        summary = "\n\n".join(summary_parts) or "Task processed by Ralph loop."
        plan_dest.write_text(
            f"""---
type: plan
task: {task_name}
agent: {agent_config.agent_id}
mode: {agent_config.mode}
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
        _move(task_path, VAULT_PATH / "Done")

    audit_logger.log_completion(task_name, turns=turn + 1, plan_written=plan_written)
    print(f"[Ralph] Finished task: {task_name} (turns={turn + 1}, mode={agent_config.mode})")


def _execute_send_approval(task_path: Path, task_name: str, content: str) -> None:
    """
    Local executes a pre-approved send/post action from a SEND_APPROVAL_* file.

    The file content contains embedded comments with the tool name and inputs:
        <!-- platinum:tool:reply_email -->
        <!-- platinum:inputs:{"message_id": "...", "body": "..."} -->
    """
    import re  # noqa: PLC0415

    tool_match = re.search(r"<!-- platinum:tool:(\S+) -->", content)
    inputs_match = re.search(r"<!-- platinum:inputs:(.+?) -->", content)

    if not tool_match or not inputs_match:
        print(
            f"[Ralph] SEND_APPROVAL missing embedded metadata in {task_name}. "
            "Cannot auto-execute. Moving to Pending_Approvals for manual review.",
            file=sys.stderr,
        )
        _move(task_path, VAULT_PATH / "Pending_Approvals")
        return

    tool_name = tool_match.group(1)
    try:
        tool_input = json.loads(inputs_match.group(1))
    except json.JSONDecodeError as exc:
        print(f"[Ralph] Failed to parse inputs in {task_name}: {exc}", file=sys.stderr)
        _move(task_path, VAULT_PATH / "Pending_Approvals")
        return

    print(f"[Ralph] Executing approved action: {tool_name} from {task_name}")
    result = call_skill(tool_name, tool_input)
    audit_logger.log(task_name, f"local_execute_{tool_name}", tool_input, result, 0)

    if result.get("ok"):
        _move(task_path, VAULT_PATH / "Done")
        print(f"[Ralph] Send approval executed and moved to Done: {task_name}")
    else:
        print(
            f"[Ralph] Send approval execution failed ({result.get('error')}): {task_name}",
            file=sys.stderr,
        )
        _move(task_path, VAULT_PATH / "Rejected")

    audit_logger.log_completion(task_name, turns=1, plan_written=False)
