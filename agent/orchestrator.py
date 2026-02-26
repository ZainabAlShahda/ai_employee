"""
orchestrator.py — Scans Needs_Action/ every 60s and dispatches items to ralph_loop.

Platinum Tier changes:
- Domain subfolder scanning: Cloud scans email/ and social/; Local scans finance/,
  files/, and the root. Local also picks up Approved/SEND_APPROVAL_* items.
- Agent-specific In_Progress: claims go to In_Progress/<agent_id>/ so Cloud and
  Local never race on the same directory listing.

Gold Tier behaviour retained:
- Uses ThreadPoolExecutor (max 3 concurrent tasks)
- Retries failed tasks up to 3 times (_retry_N suffix)
- Unrecoverable tasks move to Rejected/
- All events logged via audit_logger
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from agent_platform.config import agent_config  # noqa: E402

VAULT_PATH = agent_config.vault_path
NEEDS_ACTION = VAULT_PATH / "Needs_Action"
IN_PROGRESS = VAULT_PATH / "In_Progress"
IN_PROGRESS_AGENT = IN_PROGRESS / agent_config.agent_id
REJECTED = VAULT_PATH / "Rejected"
SCAN_INTERVAL = 60  # seconds
MAX_WORKERS = 3
MAX_RETRIES = 3

# Domains each agent mode is responsible for
DOMAIN_MAP: dict[str, list[str]] = {
    "cloud": ["email", "social"],
    "local": ["finance", "files"],
}


def _retry_count(path: Path) -> int:
    """Extract retry count from filename suffix like _retry_2."""
    stem = path.stem
    if "_retry_" in stem:
        try:
            return int(stem.rsplit("_retry_", 1)[1])
        except ValueError:
            pass
    return 0


def _in_progress_names() -> set[str]:
    IN_PROGRESS_AGENT.mkdir(parents=True, exist_ok=True)
    return {p.name for p in IN_PROGRESS_AGENT.glob("*.md")}


def _process_task(task_path: Path) -> None:
    """Run ralph_loop for one task. Called in thread pool."""
    from agent.ralph_loop import run  # noqa: PLC0415
    from audit.logger import audit_logger  # noqa: PLC0415

    retries = _retry_count(task_path)
    try:
        run(task_path)
    except Exception as exc:
        audit_logger.log(task_path.name, "orchestrator_error", {}, {"ok": False, "error": str(exc)}, 0)
        print(f"[Orch] Task failed: {task_path.name} — {exc}", file=sys.stderr)

        # Determine actual current location of the file (ralph_loop may have moved it)
        candidate_in_progress = IN_PROGRESS_AGENT / task_path.name

        if retries >= MAX_RETRIES:
            # Give up — move to Rejected
            REJECTED.mkdir(parents=True, exist_ok=True)
            rejected_path = REJECTED / task_path.name
            if candidate_in_progress.exists():
                candidate_in_progress.rename(rejected_path)
            elif task_path.exists():
                task_path.rename(rejected_path)
            print(f"[Orch] Task rejected after {MAX_RETRIES} retries: {task_path.name}")
        else:
            # Return to Needs_Action with retry suffix
            stem = task_path.stem
            base = stem.rsplit("_retry_", 1)[0] if "_retry_" in stem else stem
            new_name = f"{base}_retry_{retries + 1}.md"
            retry_path = NEEDS_ACTION / new_name
            if candidate_in_progress.exists():
                candidate_in_progress.rename(retry_path)
            elif task_path.exists():
                task_path.rename(retry_path)
            print(f"[Orch] Queued retry {retries + 1}/{MAX_RETRIES}: {new_name}")


def _collect_candidates() -> list[Path]:
    """
    Gather all task files this agent mode should process.

    Cloud  → Needs_Action/email/*.md + Needs_Action/social/*.md
    Local  → Needs_Action/*.md (root) + Needs_Action/finance/*.md
             + Needs_Action/files/*.md + Approved/SEND_APPROVAL_*.md
    """
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    candidates: list[Path] = []

    # Root-level items (both modes see root for backward-compat; Local owns them)
    if agent_config.mode == "local":
        candidates += sorted(NEEDS_ACTION.glob("*.md"))

    # Domain subfolders
    for domain in DOMAIN_MAP.get(agent_config.mode, []):
        domain_dir = NEEDS_ACTION / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        candidates += sorted(domain_dir.glob("*.md"))

    # Local picks up approval items that Cloud drafted
    if agent_config.mode == "local":
        approved_dir = VAULT_PATH / "Approved"
        approved_dir.mkdir(parents=True, exist_ok=True)
        candidates += sorted(approved_dir.glob("SEND_APPROVAL_*.md"))

    return candidates


def scan_and_dispatch(executor: ThreadPoolExecutor) -> list:
    """Scan candidate paths and submit new tasks to the executor."""
    in_progress = _in_progress_names()
    futures = []

    for md_file in _collect_candidates():
        if md_file.name in in_progress:
            continue
        print(f"[Orch] Dispatching: {md_file.name} (from {md_file.parent.name}/)")
        future = executor.submit(_process_task, md_file)
        futures.append(future)

    return futures


def main() -> None:
    print(
        f"[Orch] Orchestrator started. mode={agent_config.mode}, "
        f"agent_id={agent_config.agent_id}, "
        f"scanning every {SCAN_INTERVAL}s."
    )
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    IN_PROGRESS_AGENT.mkdir(parents=True, exist_ok=True)
    REJECTED.mkdir(parents=True, exist_ok=True)

    pending_futures: list = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while True:
            try:
                # Collect results of completed futures
                still_pending = []
                for f in pending_futures:
                    if f.done():
                        try:
                            f.result()
                        except Exception as exc:
                            print(f"[Orch] Future error: {exc}", file=sys.stderr)
                    else:
                        still_pending.append(f)
                pending_futures = still_pending

                # Only dispatch if we have capacity
                if len(pending_futures) < MAX_WORKERS:
                    new_futures = scan_and_dispatch(executor)
                    pending_futures.extend(new_futures)

            except Exception as exc:
                print(f"[Orch] Scan error: {exc}", file=sys.stderr)

            time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
