"""
sync/vault_sync.py — Git pull/commit/push loop for the Obsidian vault.

If GIT_VAULT_REMOTE is empty, all operations are silent no-ops so the
system works identically in single-machine (Gold) mode.

Run standalone:
    uv run python sync/vault_sync.py
"""

from __future__ import annotations

import fnmatch
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_platform.config import agent_config  # noqa: E402

# Patterns for files that must never be committed to the vault remote.
# Matched against the basename of each staged path.
BLOCKED_SYNC_PATTERNS: list[str] = [
    ".env",
    "*.env",
    "credentials.json",
    "token.json",
    "*_session.json",
    "seen_*.json",
    "*.key",
    "*.pem",
]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(agent_config.vault_git_path), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def pull_vault() -> None:
    """Pull latest changes from remote (rebase to avoid merge commits)."""
    if not agent_config.git_vault_remote:
        return
    result = _git("pull", "--rebase", check=False)
    if result.returncode != 0:
        print(f"[Sync] pull error: {result.stderr.strip()}", file=sys.stderr)


def _check_staged_for_secrets() -> list[str]:
    """Return a list of staged filenames that match a blocked pattern.

    Called after ``git add -A`` and before committing so that secrets
    accidentally dropped into the vault never reach the remote.
    """
    result = _git("diff", "--cached", "--name-only", check=False)
    staged = result.stdout.strip().splitlines()
    return [
        f for f in staged
        if any(fnmatch.fnmatch(Path(f).name, pat) for pat in BLOCKED_SYNC_PATTERNS)
    ]


def push_vault(message: str = "vault sync") -> None:
    """Stage all changes, commit if any, and push to remote."""
    if not agent_config.git_vault_remote:
        return
    _git("add", "-A")
    blocked = _check_staged_for_secrets()
    if blocked:
        print(
            f"[Sync] BLOCKED — refusing to sync secret files: {blocked}",
            file=sys.stderr,
        )
        _git("reset", "HEAD", check=False)  # unstage everything
        return
    diff = _git("diff", "--cached", "--quiet", check=False)
    if diff.returncode == 0:
        return  # nothing staged
    commit_result = _git("commit", "-m", message, check=False)
    if commit_result.returncode != 0:
        print(f"[Sync] commit error: {commit_result.stderr.strip()}", file=sys.stderr)
        return
    push_result = _git("push", check=False)
    if push_result.returncode != 0:
        print(f"[Sync] push error: {push_result.stderr.strip()}", file=sys.stderr)
    else:
        print(f"[Sync] pushed: {message}")


def sync_once(label: str = "") -> None:
    """Single pull → push cycle. Safe to call from external code."""
    pull_vault()
    push_vault(f"auto-sync {label or _ts()}")


def sync_loop() -> None:
    """Run sync_once every SYNC_INTERVAL seconds forever."""
    interval = agent_config.sync_interval
    print(
        f"[Sync] Starting vault sync loop "
        f"(remote={'set' if agent_config.git_vault_remote else 'none'}, "
        f"interval={interval}s)"
    )
    while True:
        try:
            sync_once()
        except Exception as exc:
            print(f"[Sync] Error: {exc}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    sync_loop()
