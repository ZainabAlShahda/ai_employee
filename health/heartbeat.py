"""
health/heartbeat.py — Writes Logs/heartbeat.json every HEARTBEAT_INTERVAL seconds.

The file records the current timestamp, agent mode, and PID so that monitoring
tools (or a human) can confirm the agent is alive.

Run standalone:
    uv run python health/heartbeat.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from platform.config import agent_config  # noqa: E402


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_heartbeat() -> None:
    """Write a single heartbeat snapshot to Logs/heartbeat.json."""
    hb = {
        "ts": _ts(),
        "mode": agent_config.mode,
        "agent_id": agent_config.agent_id,
        "pid": os.getpid(),
    }
    hb_path = agent_config.vault_path / "Logs" / "heartbeat.json"
    hb_path.parent.mkdir(parents=True, exist_ok=True)
    hb_path.write_text(json.dumps(hb, indent=2), encoding="utf-8")


def heartbeat_loop() -> None:
    """Write heartbeat.json every HEARTBEAT_INTERVAL seconds."""
    interval = agent_config.heartbeat_interval
    print(
        f"[Heartbeat] Started (mode={agent_config.mode}, "
        f"interval={interval}s, pid={os.getpid()})"
    )
    while True:
        try:
            write_heartbeat()
        except Exception as exc:
            print(f"[Heartbeat] Error: {exc}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    heartbeat_loop()
