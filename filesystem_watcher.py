
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import shutil

class DropFolderHandler(FileSystemEventHandler):
    def __init__(self, vault_path: str):
        self.needs_action = Path(vault_path) / 'Needs_Action'

    def on_created(self, event):
        if event.is_directory:
            return
        source = Path(event.src_path)
        dest = self.needs_action / f'FILE_{source.name}'
        shutil.copy2(source, dest)
        self.create_metadata(source, dest)

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
    vault_path = "/path/to/AI_Employee_Vault"
    event_handler = DropFolderHandler(vault_path)
    observer = Observer()
    observer.schedule(event_handler, "/path/to/drop_folder", recursive=False)
    observer.start()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

