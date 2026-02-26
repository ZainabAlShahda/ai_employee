"""
sync/dashboard_merger.py — Merges Updates/*.md snippets into Dashboard.md.

Local-only operation. Cloud agents write snippets to Updates/; Local reads
and appends them to Dashboard.md under an ## Updates section, then deletes
the source files.

Run standalone (for testing):
    uv run python sync/dashboard_merger.py
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_platform.config import agent_config  # noqa: E402


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_updates_section(dashboard_text: str) -> str:
    """Ensure Dashboard.md contains an ## Updates section at the end."""
    if "## Updates" not in dashboard_text:
        return dashboard_text.rstrip() + "\n\n## Updates\n"
    return dashboard_text


def _append_to_dashboard(dashboard_path: Path, content: str, source_name: str) -> None:
    existing = dashboard_path.read_text(encoding="utf-8") if dashboard_path.exists() else ""
    existing = _ensure_updates_section(existing)
    snippet = f"\n### {source_name} — {_ts()}\n\n{content.strip()}\n"
    dashboard_path.write_text(existing + snippet, encoding="utf-8")


def merge_updates() -> None:
    """
    Merge all files in Updates/ into Dashboard.md.
    No-op when called in cloud mode (Local is single-writer for Dashboard).
    """
    if agent_config.mode != "local":
        return

    vault_path = agent_config.vault_path
    updates_dir = vault_path / "Updates"
    dashboard = vault_path / "Dashboard.md"

    if not updates_dir.exists():
        return

    merged = 0
    for update_file in sorted(updates_dir.glob("*.md")):
        try:
            content = update_file.read_text(encoding="utf-8")
            _append_to_dashboard(dashboard, content, update_file.stem)
            update_file.unlink()
            merged += 1

            try:
                from audit.logger import audit_logger  # noqa: PLC0415
                audit_logger.log(
                    "dashboard_merger",
                    "merge_update",
                    {"file": update_file.name},
                    {"ok": True},
                    0,
                )
            except Exception:
                pass  # audit failure must not block merging

        except Exception as exc:
            print(f"[Merger] Failed to merge {update_file.name}: {exc}", file=sys.stderr)

    if merged:
        print(f"[Merger] Merged {merged} update(s) into Dashboard.md")


def merge_loop(interval: int = 60) -> None:
    """Run merge_updates() every `interval` seconds."""
    print(f"[Merger] Dashboard merger started (interval={interval}s)")
    while True:
        try:
            merge_updates()
        except Exception as exc:
            print(f"[Merger] Error: {exc}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    merge_updates()
    print("[Merger] Done (single pass).")
