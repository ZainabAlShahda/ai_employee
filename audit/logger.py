"""
logger.py — Structured JSONL audit logger.

Appends one JSON object per line to AI_Employee_Vault/Logs/audit.jsonl.
Thread-safe via a threading.Lock.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

VAULT_PATH = Path(os.getenv("VAULT_PATH", r"E:\ai_employee\AI_Employee_Vault"))
LOG_DIR = VAULT_PATH / "Logs"
LOG_FILE = LOG_DIR / "audit.jsonl"

_lock = threading.Lock()


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class AuditLogger:
    """Singleton-style audit logger. Use the module-level `audit_logger` instance."""

    def log(
        self,
        task: str,
        action: str,
        inputs: dict,
        result: dict,
        agent_turn: int = 0,
    ) -> None:
        """Log a single tool-use action."""
        record = {
            "ts": _ts(),
            "task": task,
            "action": action,
            "input": inputs,
            "result": result,
            "agent_turn": agent_turn,
        }
        _append(record)

    def log_completion(self, task: str, turns: int = 0, plan_written: bool = False) -> None:
        """Log task completion."""
        record = {
            "ts": _ts(),
            "task": task,
            "action": "task_completed",
            "input": {},
            "result": {"ok": True, "turns": turns, "plan_written": plan_written},
            "agent_turn": turns,
        }
        _append(record)

    def log_error(self, task: str, error: str, agent_turn: int = 0) -> None:
        """Log an unhandled error."""
        record = {
            "ts": _ts(),
            "task": task,
            "action": "error",
            "input": {},
            "result": {"ok": False, "error": error},
            "agent_turn": agent_turn,
        }
        _append(record)

    def read_last_n_days(self, days: int = 7) -> list[dict]:
        """Return audit records from the last N days."""
        from datetime import timedelta  # noqa: PLC0415

        if not LOG_FILE.exists():
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        records = []
        with LOG_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    ts = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
                    if ts >= cutoff:
                        records.append(rec)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        return records


# Module-level singleton
audit_logger = AuditLogger()
