# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI Employee** system (Platinum Tier) — two cooperating agents (Cloud + Local) share state exclusively through a Git-synced Obsidian vault. Cloud runs 24/7, triages email and social, and drafts actions. Local owns all final sends, payments, and approvals. Python watcher scripts monitor external inputs and route events into the vault; a Claude-powered Ralph Wiggum loop autonomously processes them using MCP tools; everything is logged to `audit.jsonl`. Weekly CEO briefings are auto-generated from vault stats and Odoo accounting data.

## Environment & Package Management

- Python 3.13 (enforced via `.python-version`)
- Package manager: **uv** (not pip or conda)
- Install dependencies: `uv sync`
- Run a script: `uv run python <script>.py`
- Add a dependency: `uv add <package>`

## Architecture

### Platinum Tier File Tree

```
E:/ai_employee/
├── platform/                   Agent identity + capability management
│   ├── config.py               AgentConfig singleton — reads AGENT_MODE from .env
│   └── capabilities.py         Per-mode allowed skills list + draft-only flag
│
├── sync/                       Vault git synchronisation
│   ├── vault_sync.py           git pull/commit/push loop
│   └── dashboard_merger.py     Merges Updates/*.md → Dashboard.md (Local only)
│
├── health/                     Process health
│   ├── monitor.py              Subprocess watchdog — restarts dead processes
│   └── heartbeat.py            Writes Logs/heartbeat.json every HEARTBEAT_INTERVAL s
│
├── deploy/                     Cloud deployment
│   ├── docker-compose.yml      Odoo 17 + PostgreSQL 16 + Caddy + backup + agent
│   ├── Caddyfile               Caddy reverse proxy + auto-TLS config
│   ├── Dockerfile.agent        Python 3.13-slim image with uv
│   ├── supervisord.conf        Non-Docker fallback process manager
│   ├── setup_cloud.sh          One-shot cloud VM bootstrap script
│   └── backups/                pg_dump output directory (.gitkeep, *.sql excluded)
│
├── watchers/                   Social media watchers (Facebook, Instagram, Twitter)
├── mcp_servers/                MCP servers (gmail_mcp, odoo_mcp, social_mcp)
├── agent/                      Claude reasoning loop (orchestrator, ralph_loop, skills, prompts)
├── audit/                      Structured JSONL audit logger
├── scheduler/                  Weekly CEO briefing generator
└── AI_Employee_Vault/          Obsidian vault (shared state bus between Cloud and Local)
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

### Agent Pipeline (Platinum Tier)

```
[Cloud]
Needs_Action/email|social/ → orchestrator → ralph_loop (cloud mode)
                                                ↓ draft-only gate
                                         Pending_Approvals/SEND_APPROVAL_*.md
                                                ↓ vault_sync git push

[Local — user approves in Obsidian]
Approved/SEND_APPROVAL_*.md → orchestrator → ralph_loop (local mode)
                                                ↓ _execute_send_approval
                                           mcp_servers/ (gmail, odoo, social)
                                                ↓
                                          Done/ + Plans/ + audit.jsonl
```

- **orchestrator.py**: Domain-aware scanner. Cloud scans `Needs_Action/email/` and `social/`; Local scans root, `finance/`, `files/`, and `Approved/SEND_APPROVAL_*`. Claims go to `In_Progress/<agent_id>/`. ThreadPoolExecutor(max_workers=3), 3 retries before `Rejected/`.
- **ralph_loop.py**: Max 10 Claude turns. Cloud mode intercepts `SEND_TOOLS` → `request_approval` with embedded `<!-- platinum:tool/inputs -->` metadata. Local mode detects `SEND_APPROVAL_*` files and calls `_execute_send_approval()` directly (no Claude turn needed).
- **skills.py**: Maps 13 tool names → Python callables. Returns `{"ok": True/False, ...}`. In cloud mode, `call_skill()` hard-blocks `SEND_TOOLS` as a safety net.
- **prompts.py**: `SYSTEM_PROMPT` (full access) + `CLOUD_SYSTEM_PROMPT` (draft-only rules appended) + `BRIEFING_PROMPT`.

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

The vault is an Obsidian vault and the **sole communication bus** between Cloud and Local agents. Both agents sync it via git (`sync/vault_sync.py`).

```
Needs_Action/
  ├── email/      ← Gmail watcher drops here (Cloud picks up)
  ├── social/     ← Social watchers drop here (Cloud picks up)
  ├── finance/    ← Payment/invoice items (Local picks up)
  ├── files/      ← Filesystem watcher (Local picks up)
  └── *.md        ← Root items (Local picks up, backward-compat)
In_Progress/
  ├── cloud/      ← Cloud claims here (claim-by-move)
  └── local/      ← Local claims here (claim-by-move)
Pending_Approvals/ ← Items requiring human sign-off (payments > $500, cloud drafts)
Approved/          ← Human-approved items; SEND_APPROVAL_* picked up by Local
Rejected/          ← Failed / abandoned tasks
Plans/             ← Task plans written by ralph_loop
Done/              ← Completed tasks
Logs/              ← audit.jsonl + heartbeat.json
Updates/           ← Cloud writes dashboard snippets; Local merges → Dashboard.md
```

Key vault documents:
- `Dashboard.md` — Live status overview (single-writer: Local). Cloud snippets go to `Updates/`.
- `Company_Handbook.md` — Operating rules (finance thresholds, communication tone, task routing logic)

#### SEND_APPROVAL flow

Cloud embeds tool metadata in approval files:
```markdown
<!-- platinum:tool:reply_email -->
<!-- platinum:inputs:{"message_id": "...", "body": "..."} -->
```
Local's `_execute_send_approval()` parses these and calls `call_skill()` directly.

### Security Rules (Platinum #4 — Secrets Never Sync)

Three independent layers prevent secrets from reaching the vault remote:

1. **`AI_Employee_Vault/.gitignore`** — vault-level ignore list. Even if the vault is managed as a
   standalone git repo, blocked patterns (`.env`, `credentials.json`, `*.key`, `*.pem`, etc.) are
   never staged.
2. **`sync/vault_sync.py` pre-push scan** — `_check_staged_for_secrets()` inspects staged files
   after `git add -A` and before committing. Aborts with `git reset HEAD` if any blocked file is
   staged.
3. **`platform/capabilities.py` capability gate** — Cloud never loads WhatsApp sessions, banking
   credentials, or payment tokens. `SEND_TOOLS` + `DRAFT_ONLY_MODE` enforce this in code;
   `call_skill()` raises a hard error if a SEND_TOOL is invoked in cloud mode.

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
- **Caddy / HTTPS**: Set `ODOO_DOMAIN=odoo.yourdomain.com` — Caddy uses this for automatic Let's Encrypt certificate provisioning.
- `credentials.json` and `.env` must never be committed.

## Odoo Setup

1. Download Odoo 17 Community (or use the Docker image in `deploy/docker-compose.yml`)
2. Install PostgreSQL 16+ locally (or let Docker Compose manage it)
3. Default port 8069; set `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD` in `.env`
4. Odoo MCP authenticates via `POST /web/session/authenticate` (JSON-RPC 2.0)

## Running the System

### Local mode (single machine, Gold-compatible)

```bash
uv sync

# Option A — start everything via monitor (recommended)
uv run python health/monitor.py

# Option B — start components individually
uv run python agent/orchestrator.py
uv run python filesystem_watcher.py
uv run python gmail_watcher.py
uv run python sync/vault_sync.py      # only needed if GIT_VAULT_REMOTE is set
uv run python health/heartbeat.py

# Generate CEO briefing now
uv run python scheduler/weekly_briefing.py
```

### Cloud mode (Docker)

```bash
# On the cloud VM (after running deploy/setup_cloud.sh):
cd /app
docker compose -f deploy/docker-compose.yml up -d

# View agent logs
docker compose -f deploy/docker-compose.yml logs -f agent
```

### Cloud mode (no Docker — supervisord)

```bash
AGENT_MODE=cloud uv run python health/monitor.py
# or via supervisord:
supervisord -c deploy/supervisord.conf
```

### Platinum Tier — full two-agent flow

```
.env: AGENT_MODE=cloud  GIT_VAULT_REMOTE=<ssh-url>  (on cloud VM)
.env: AGENT_MODE=local  GIT_VAULT_REMOTE=<ssh-url>  (on local machine)
```

1. Cloud VM: `docker compose up -d` — starts monitor → orchestrator + watchers + vault_sync
2. Local: `uv run python health/monitor.py` — starts orchestrator + vault_sync + dashboard_merger
3. Email arrives → Cloud triages → drafts reply → `Pending_Approvals/SEND_APPROVAL_*.md` → git push
4. Local pulls → user reviews in Obsidian → moves file to `Approved/`
5. Local orchestrator picks up `Approved/SEND_APPROVAL_*` → executes via Gmail MCP → `Done/`

## Project Tier Requirements

This project is structured around four capability tiers:

### Bronze Tier — Basic Automation (0–10 hrs)

The implicit foundation that all higher tiers build on:
- Single watcher script monitoring one input channel (e.g., a local folder or inbox)
- Write incoming events as Markdown files to a local vault folder
- No Claude reasoning loop — purely mechanical routing
- No external actions (read-only / observe mode)
- Manual review of vault files by the operator

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
- Lessons learned documentation (`docs/lessons_learned.md`) ✅

### Platinum Tier — Always-On Cloud + Local Executive (60+ hrs) ✅
- Run the AI Employee on Cloud 24/7 (always-on watchers + orchestrator + health monitoring) ✅
- **Work-Zone Specialization:** ✅
  - Cloud owns: email triage, draft replies, social post drafts/scheduling (draft-only; requires Local approval before send/post)
  - Local owns: approvals, WhatsApp session, payments/banking, and final send/post actions
- **Delegation via Synced Vault:** ✅
  - Agents communicate via files in `Needs_Action/<domain>/`, `In_Progress/<agent_id>/`, `Approved/SEND_APPROVAL_*/`
  - Claim-by-move rule: first agent to move an item from `Needs_Action/` to `In_Progress/<agent_id>/` owns it
  - `Dashboard.md` is single-writer (Local); Cloud writes to `Updates/` and Local merges via `dashboard_merger.py`
  - Vault sync via Git (`sync/vault_sync.py`) — markdown/state only, secrets never sync
- **Secrets-never-sync (security rule):** ✅
  - `AI_Employee_Vault/.gitignore` — blocks `.env`, `credentials.json`, `token.json`, `*.key`, `*.pem`, etc. at vault repo level
  - `sync/vault_sync.py` pre-push scan — `_check_staged_for_secrets()` aborts and unstages if any blocked file would be committed
  - `platform/capabilities.py` — Cloud never holds WhatsApp sessions, banking credentials, or payment tokens; enforced by `SEND_TOOLS` + `DRAFT_ONLY_MODE`
- **Odoo HTTPS + automated backups:** ✅
  - Caddy reverse proxy (`deploy/Caddyfile`) handles automatic Let's Encrypt TLS — set `ODOO_DOMAIN` in `.env`
  - pg_dump backup sidecar in `docker-compose.yml` — daily dumps to `deploy/backups/`, retains last 7
- Deploy Odoo Community on Cloud VM via Docker Compose (`deploy/`) ✅
- Process watchdog (`health/monitor.py`) restarts any dead subprocess automatically ✅
- Heartbeat (`health/heartbeat.py`) writes `Logs/heartbeat.json` for liveness monitoring ✅
- Optional A2A Upgrade (Phase 2): replace file handoffs with direct A2A messages while keeping vault as audit record
- **Platinum passing gate:** Email arrives while Local is offline → Cloud drafts reply + writes approval file → vault syncs via git → user approves on Local return → Local sends via MCP → logs → moves to `Done/` ✅

## Company Operating Rules (from Handbook)

When implementing new features or AI logic, follow the rules in `Company_Handbook.md`:
- Transactions > $500 → route to `Pending_Approvals/`
- Transactions ≤ $500 → route to `Approved/` and log
- All actions must be logged in `Logs/`
- Completed tasks move to `Done/`
- No external cloud storage unless explicitly approved; all data stays in the local vault
