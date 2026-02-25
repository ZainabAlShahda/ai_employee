"""
orchestrator.py — Scans Needs_Action/ every 60s and dispatches items to ralph_loop.

- Uses ThreadPoolExecutor (max 3 concurrent tasks)
- Retries failed tasks up to 3 times (_retry_N suffix)
- Unrecoverable tasks move to Rejected/
- All events logged via audit_logger
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

VAULT_PATH = Path(os.getenv("VAULT_PATH", r"E:\ai_employee\AI_Employee_Vault"))
NEEDS_ACTION = VAULT_PATH / "Needs_Action"
IN_PROGRESS = VAULT_PATH / "In_Progress"
REJECTED = VAULT_PATH / "Rejected"
SCAN_INTERVAL = 60  # seconds
MAX_WORKERS = 3
MAX_RETRIES = 3


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
    IN_PROGRESS.mkdir(parents=True, exist_ok=True)
    return {p.name for p in IN_PROGRESS.glob("*.md")}


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

        if retries >= MAX_RETRIES:
            # Give up — move to Rejected
            REJECTED.mkdir(parents=True, exist_ok=True)
            rejected_path = REJECTED / task_path.name
            # File may have been moved to In_Progress by ralph_loop already
            candidate = IN_PROGRESS / task_path.name
            if candidate.exists():
                candidate.rename(rejected_path)
            elif task_path.exists():
                task_path.rename(rejected_path)
            print(f"[Orch] Task rejected after {MAX_RETRIES} retries: {task_path.name}")
        else:
            # Return to Needs_Action with retry suffix
            stem = task_path.stem
            if "_retry_" in stem:
                base = stem.rsplit("_retry_", 1)[0]
            else:
                base = stem
            new_name = f"{base}_retry_{retries + 1}.md"
            retry_path = NEEDS_ACTION / new_name
            candidate = IN_PROGRESS / task_path.name
            if candidate.exists():
                candidate.rename(retry_path)
            elif task_path.exists():
                task_path.rename(retry_path)
            print(f"[Orch] Queued retry {retries + 1}/{MAX_RETRIES}: {new_name}")


def scan_and_dispatch(executor: ThreadPoolExecutor) -> list:
    """Scan Needs_Action/ and submit new tasks to the executor."""
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    in_progress = _in_progress_names()
    futures = []

    for md_file in sorted(NEEDS_ACTION.glob("*.md")):
        if md_file.name in in_progress:
            continue
        print(f"[Orch] Dispatching: {md_file.name}")
        future = executor.submit(_process_task, md_file)
        futures.append(future)

    return futures


def main() -> None:
    print(f"[Orch] Orchestrator started. Scanning {NEEDS_ACTION} every {SCAN_INTERVAL}s.")
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    IN_PROGRESS.mkdir(parents=True, exist_ok=True)
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
