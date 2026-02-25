"""
platform/config.py — AgentConfig singleton.

Reads AGENT_MODE (and related env vars) once at import time.
All other modules import `agent_config` from here.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AgentConfig:
    mode: str              # "cloud" | "local"
    vault_path: Path
    agent_id: str          # same as mode; used for In_Progress/<agent_id>/
    git_vault_remote: str  # SSH/HTTPS URL for vault repo (empty = no-op sync)
    vault_git_path: Path   # root of vault git repo
    heartbeat_interval: int
    sync_interval: int


def _default_vault() -> str:
    return os.getenv("VAULT_PATH", r"E:\ai_employee\AI_Employee_Vault")


agent_config = AgentConfig(
    mode=os.getenv("AGENT_MODE", "local"),
    vault_path=Path(_default_vault()),
    agent_id=os.getenv("AGENT_MODE", "local"),
    git_vault_remote=os.getenv("GIT_VAULT_REMOTE", ""),
    vault_git_path=Path(os.getenv("VAULT_GIT_PATH", _default_vault())),
    heartbeat_interval=int(os.getenv("HEARTBEAT_INTERVAL", "30")),
    sync_interval=int(os.getenv("SYNC_INTERVAL", "60")),
)


if __name__ == "__main__":
    print(agent_config)
