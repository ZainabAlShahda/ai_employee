# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI Employee** system — a collection of Python watcher scripts that monitor external inputs (filesystem, Gmail, WhatsApp, LinkedIn) and route detected events into a local Obsidian vault for processing. The vault acts as the AI employee's "brain" and task management system.

## Environment & Package Management

- Python 3.13 (enforced via `.python-version`)
- Package manager: **uv** (not pip or conda)
- Install dependencies: `uv sync`
- Run a script: `uv run python <script>.py`
- Add a dependency: `uv add <package>`

## Architecture

### Watcher Scripts → Vault Pipeline

Each watcher script monitors a specific input channel and writes Markdown files (with YAML frontmatter) into `AI_Employee_Vault/Needs_Action/` when new events are detected:

| Script | Input Channel | Mechanism |
|---|---|---|
| `filesystem_watcher.py` | `E:\AI_Dropbox` folder | `watchdog` filesystem events |
| `gmail_watcher.py` | Gmail inbox | Google Gmail API polling (30s interval) |
| `whatsapp_watcher.py` | WhatsApp Web | Playwright browser automation |
| `linkedin_watcher.py` | LinkedIn notifications | Playwright browser automation |

Each script runs independently and indefinitely (loop + sleep). They are not orchestrated — each must be started manually.

### Vault Structure (`AI_Employee_Vault/`)

The vault is an Obsidian vault with the following workflow folders:

```
Needs_Action/   ← Watchers drop items here (prefixed GMAIL_, FILE_, WHATSAPP_, LINKEDIN_)
Inbox/          ← General inbox
Pending_Approvals/ ← Items requiring human sign-off (e.g. payments > $500)
Approved/       ← Approved items
Rejected/       ← Rejected items
Plans/          ← Task plans
Done/           ← Completed items
Logs/           ← Action logs
```

Key vault documents:
- `Dashboard.md` — Live status overview (tasks, finance summary, communications)
- `Company_Handbook.md` — Operating rules (finance thresholds, communication tone, task routing logic)

### Metadata Format

All items dropped into the vault use YAML frontmatter:
```yaml
---
type: gmail_message | file_drop | whatsapp_chat | linkedin_notification
id/name/subject/from: ...
---
```

## Authentication

- **Gmail**: OAuth2 via `credentials.json` (Google Cloud project). On first run, a browser window opens for consent. Token is saved to `token.json` (gitignored).
- **WhatsApp / LinkedIn**: Playwright opens a headed Chromium browser; manual QR scan / login required on each run.
- `credentials.json` is gitignored and must not be committed.

## Company Operating Rules (from Handbook)

When implementing new features or AI logic, follow the rules in `Company_Handbook.md`:
- Transactions > $500 → route to `Pending_Approvals/`
- Transactions ≤ $500 → route to `Approved/` and log
- All actions must be logged in `Logs/`
- Completed tasks move to `Done/`
- No external cloud storage unless explicitly approved; all data stays in the local vault
