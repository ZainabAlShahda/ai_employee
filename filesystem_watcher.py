from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import shutil
import time
import os

class DropFolderHandler(FileSystemEventHandler):
    def __init__(self, vault_path: str):
        self.needs_action = Path(vault_path) / 'Needs_Action'
        self.needs_action.mkdir(parents=True, exist_ok=True)

    def on_created(self, event):
        if event.is_directory:
            return
        source = Path(event.src_path)
        dest = self.needs_action / f'FILE_{source.name}'
        print(f"📂 Detected new file: {source.name}, waiting until it is free...")

        # Retry until the file is not locked
        for attempt in range(10):
            try:
                shutil.copy2(source, dest)
                self.create_metadata(source, dest)
                print(f"✅ Copied {source.name} → Needs_Action")
                break
            except PermissionError:
                print(f"⚠️ File {source.name} is locked, retrying ({attempt+1}/10)...")
                time.sleep(1)
        else:
            print(f"❌ Failed to copy {source.name} after 10 attempts.")

    def create_metadata(self, source: Path, dest: Path):
        meta_path = dest.with_suffix('.md')
        meta_path.write_text(f"""---
type: file_drop
original_name: {source.name}
size: {source.stat().st_size}
---

New file dropped for processing.
""")

if __name__ == "__main__":
    vault_path = r"E:\ai_employee\AI_Employee_Vault"
    drop_folder = r"E:\AI_Dropbox"

    event_handler = DropFolderHandler(vault_path)
    observer = Observer()
    observer.schedule(event_handler, drop_folder, recursive=False)
    observer.start()
    print(f"👀 Watching folder: {drop_folder}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()




