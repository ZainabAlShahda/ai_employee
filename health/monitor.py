"""
health/monitor.py — Process watchdog for the AI Employee.

Starts all managed sub-processes via subprocess.Popen and polls every 10s.
Any process that has died is restarted automatically. Restarts are logged
to the audit trail.

This is the single entry point for the cloud container:
    uv run python health/monitor.py

It also works locally as a convenience wrapper.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_platform.config import agent_config  # noqa: E402

PROJECT_ROOT = str(Path(__file__).parent.parent)
POLL_INTERVAL = 10  # seconds


def _get_managed_procs() -> list[tuple[str, list[str]]]:
    """Return (name, command) pairs for all processes this mode should run."""
    base: list[tuple[str, list[str]]] = [
        ("orchestrator", ["uv", "run", "python", "agent/orchestrator.py"]),
        ("vault_sync",   ["uv", "run", "python", "sync/vault_sync.py"]),
        ("heartbeat",    ["uv", "run", "python", "health/heartbeat.py"]),
        ("gmail_watcher",["uv", "run", "python", "gmail_watcher.py"]),
    ]

    if agent_config.mode == "cloud":
        base += [
            ("fb_watcher", ["uv", "run", "python", "watchers/facebook_watcher.py"]),
            ("ig_watcher", ["uv", "run", "python", "watchers/instagram_watcher.py"]),
            ("tw_watcher", ["uv", "run", "python", "watchers/twitter_watcher.py"]),
        ]
    else:
        # Local mode also runs the filesystem watcher
        base += [
            ("fs_watcher",      ["uv", "run", "python", "filesystem_watcher.py"]),
            ("dashboard_merger",["uv", "run", "python", "sync/dashboard_merger.py"]),
        ]

    return base


def _start(name: str, cmd: list[str]) -> subprocess.Popen:
    print(f"[Monitor] Starting: {name}")
    return subprocess.Popen(cmd, cwd=PROJECT_ROOT)


def _log_restart(name: str) -> None:
    try:
        from audit.logger import audit_logger  # noqa: PLC0415
        audit_logger.log("monitor", "restart_process", {"name": name}, {"ok": True}, 0)
    except Exception:
        pass  # audit must not prevent restart


def monitor_loop() -> None:
    managed = _get_managed_procs()
    procs: dict[str, subprocess.Popen] = {}

    # Initial start
    for name, cmd in managed:
        procs[name] = _start(name, cmd)

    print(
        f"[Monitor] Watchdog running "
        f"(mode={agent_config.mode}, processes={[n for n, _ in managed]})"
    )

    while True:
        time.sleep(POLL_INTERVAL)
        for name, cmd in managed:
            proc = procs.get(name)
            if proc is None or proc.poll() is not None:
                exit_code = proc.returncode if proc else "N/A"
                print(
                    f"[Monitor] Process '{name}' exited (code={exit_code}). Restarting...",
                    file=sys.stderr,
                )
                _log_restart(name)
                procs[name] = _start(name, cmd)


if __name__ == "__main__":
    monitor_loop()
