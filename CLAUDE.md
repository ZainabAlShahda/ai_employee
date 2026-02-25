# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI Employee** system (Gold Tier) — Python watcher scripts monitor external inputs (filesystem, Gmail, WhatsApp, LinkedIn, Facebook, Instagram, Twitter) and route events into a local Obsidian vault. A Claude-powered orchestrator (Ralph Wiggum loop) autonomously reasons over those items using MCP tools and logs everything to `audit.jsonl`. Weekly CEO briefings are auto-generated from vault stats and Odoo accounting data.

## Environment & Package Management

- Python 3.13 (enforced via `.python-version`)
- Package manager: **uv** (not pip or conda)
- Install dependencies: `uv sync`
- Run a script: `uv run python <script>.py`
- Add a dependency: `uv add <package>`

## Architecture

### Gold Tier File Tree

```
E:/ai_employee/
├── watchers/                   Social media watchers (Facebook, Instagram, Twitter)
├── mcp_servers/                MCP servers (gmail_mcp, odoo_mcp, social_mcp)
├── agent/                      Claude reasoning loop (orchestrator, ralph_loop, skills, prompts)
├── audit/                      Structured JSONL audit logger
├── scheduler/                  Weekly CEO briefing generator
└── AI_Employee_Vault/          Obsidian vault (vault state)
```

### Watcher Scripts → Vault Pipeline

Each watcher script monitors a specific input channel and writes Markdown files (with YAML frontmatter) into `AI_Employee_Vault/Needs_Action/` when new events are detected:

| Script | Input Channel | Mechanism |
|---|---|---|
| `filesystem_watcher.py` | `E:\AI_Dropbox` folder | `watchdog` filesystem events |
| `gmail_watcher.py` | Gmail inbox | Google Gmail API polling (30s interval) |
| `whatsapp_watcher.py` | WhatsApp Web | Playwright browser automation |
| `linkedin_watcher.py` | LinkedIn notifications | Playwright browser automation |
| `watchers/facebook_watcher.py` | Facebook Page feed + mentions | Meta Graph API polling (60s) |
| `watchers/instagram_watcher.py` | Instagram Business media + tags | Meta Graph API polling (60s) |
| `watchers/twitter_watcher.py` | X/Twitter mentions | Tweepy API v2 (Playwright fallback) |

Each script runs independently and indefinitely (loop + sleep). They are not orchestrated — each must be started manually.

### Agent Pipeline (Gold Tier)

```
Needs_Action/ → orchestrator.py → ralph_loop.py → Claude API (tool-use loop)
                                                       ↓ tools
                                                  mcp_servers/
                                                  (gmail, odoo, social)
                                                       ↓ results
                                               Done/ + Plans/ + audit.jsonl
```

- **orchestrator.py**: Scans `Needs_Action/` every 60s, dispatches tasks to Ralph loop via `ThreadPoolExecutor(max_workers=3)`. Retries up to 3 times; moves to `Rejected/` on failure.
- **ralph_loop.py**: Iterates Claude tool-use turns (max 10). Claims tasks by moving to `In_Progress/`. Writes Plan.md to `Plans/`. Moves completed tasks to `Done/`.
- **skills.py**: Maps 13 tool names → Python callables. Returns `{"ok": True/False, ...}`.
- **prompts.py**: System prompt with safety rules (payment gate, approval gate).

### MCP Servers

| Server | Tools |
|---|---|
| `mcp_servers/gmail_mcp.py` | `send_email`, `reply_email`, `label_email` |
| `mcp_servers/odoo_mcp.py` | `create_invoice`, `list_contacts`, `get_accounting_report`, `post_payment` |
| `mcp_servers/social_mcp.py` | `post_linkedin`, `post_facebook`, `post_instagram`, `post_twitter` |

Run a server: `uv run python mcp_servers/gmail_mcp.py`

### Weekly CEO Briefing

`scheduler/weekly_briefing.py` — generates `Plans/CEO_Briefing_<date>.md` using:
1. Odoo P&L from `get_accounting_report("last_week")`
2. Vault folder counts (Done, Approved, Rejected, Pending_Approvals)
3. Last 7 days of `audit.jsonl`
4. Claude narrative generation (claude-opus-4-6)

Run immediately: `uv run python scheduler/weekly_briefing.py`
Schedule via Windows Task Scheduler: call above every Monday at 08:45.

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

## Authentication & Secrets

All secrets live in `.env` (gitignored). Copy `.env.example` → `.env` and fill in values.

- **Gmail**: OAuth2 via `credentials.json`. On first run, browser consent flow saves `token.json` (gitignored).
- **WhatsApp / LinkedIn**: Playwright opens headed Chromium; manual QR scan / login required per run.
- **Facebook / Instagram**: Meta Graph API — set `META_ACCESS_TOKEN`, `META_PAGE_ID`, `META_IG_ACCOUNT_ID`.
- **Twitter / X**: Tweepy OAuth1 — set all 5 `TWITTER_*` env vars.
- **Odoo**: JSON-RPC — set `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD`.
- **Anthropic**: Set `ANTHROPIC_API_KEY` for the Ralph loop and CEO briefing.
- `credentials.json` and `.env` must never be committed.

## Odoo Setup (Gold Tier)

1. Download Odoo 19 Community from `https://www.odoo.com/odoo-19-download`
2. Install PostgreSQL 16+ locally
3. Run Odoo installer; default port 8069
4. Create a database; set `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD` in `.env`
5. Odoo MCP authenticates via `POST /web/session/authenticate` (JSON-RPC 2.0)

## Running the System (Gold Tier)

```bash
# Install deps
uv sync

# Start orchestrator (main loop — processes all Needs_Action items)
uv run python agent/orchestrator.py

# Start watchers (each in its own terminal or Task Scheduler job)
uv run python filesystem_watcher.py
uv run python gmail_watcher.py
uv run python watchers/facebook_watcher.py
uv run python watchers/instagram_watcher.py
uv run python watchers/twitter_watcher.py

# Generate CEO briefing now
uv run python scheduler/weekly_briefing.py
```

## Project Tier Requirements

This project is structured around four capability tiers:

### Silver Tier — Functional Assistant (20–30 hrs)
- Two or more Watcher scripts (Gmail + WhatsApp + LinkedIn) ✅
- Automatically post on LinkedIn about business to generate sales
- Claude reasoning loop that creates `Plan.md` files
- One working MCP server for external action (e.g. sending emails)
- Human-in-the-loop approval workflow for sensitive actions
- Basic scheduling via cron or Task Scheduler
- All AI functionality implemented as Agent Skills

### Gold Tier — Autonomous Employee (40+ hrs)
- Full cross-domain integration (Personal + Business)
- Accounting system in Odoo Community (self-hosted, local) integrated via MCP using Odoo's JSON-RPC APIs (Odoo 19+)
- Facebook, Instagram, Twitter (X) integration — post messages and generate summaries
- Multiple MCP servers for different action types
- Weekly Business and Accounting Audit with CEO Briefing generation
- Error recovery and graceful degradation
- Comprehensive audit logging
- Ralph Wiggum loop for autonomous multi-step task completion
- All AI functionality implemented as Agent Skills

### Platinum Tier — Always-On Cloud + Local Executive (60+ hrs)
- Run the AI Employee on Cloud 24/7 (always-on watchers + orchestrator + health monitoring)
- **Work-Zone Specialization:**
  - Cloud owns: email triage, draft replies, social post drafts/scheduling (draft-only; requires Local approval before send/post)
  - Local owns: approvals, WhatsApp session, payments/banking, and final send/post actions
- **Delegation via Synced Vault:**
  - Agents communicate via files in `/Needs_Action/<domain>/`, `/Plans/<domain>/`, `/Pending_Approval/<domain>/`
  - Claim-by-move rule: first agent to move an item from `/Needs_Action/` to `/In_Progress/<agent>/` owns it
  - `Dashboard.md` is single-writer (Local); Cloud writes to `/Updates/` and Local merges
  - Vault sync via Git or Syncthing (markdown/state only — secrets never sync)
- Deploy Odoo Community on Cloud VM (24/7) with HTTPS, backups, and health monitoring
- Optional A2A Upgrade (Phase 2): replace file handoffs with direct A2A messages while keeping vault as audit record
- **Platinum passing gate:** Email arrives while Local is offline → Cloud drafts reply + writes approval file → user approves on Local return → Local sends via MCP → logs → moves to `/Done/`

## Company Operating Rules (from Handbook)

When implementing new features or AI logic, follow the rules in `Company_Handbook.md`:
- Transactions > $500 → route to `Pending_Approvals/`
- Transactions ≤ $500 → route to `Approved/` and log
- All actions must be logged in `Logs/`
- Completed tasks move to `Done/`
- No external cloud storage unless explicitly approved; all data stays in the local vault
