# AI Employee — Platinum Tier

An always-on autonomous AI system that monitors email, social media, and files; drafts responses using Claude; manages Odoo accounting; and executes approved actions — all while keeping a human in the loop for anything sensitive.

Two cooperating agents (**Cloud** + **Local**) share state exclusively through a Git-synced Obsidian vault. Cloud runs 24/7 and drafts actions. Local owns all final sends, payments, and approvals.

---

## How It Works

```
[Inputs]                         [Vault]                       [Outputs]
Gmail  ────────────────────→  Needs_Action/email/   →  Cloud drafts reply
Facebook / Instagram / X ──→  Needs_Action/social/  →  Cloud drafts post
File Drop (AI_Dropbox)  ───→  Needs_Action/files/   →  Local processes
WhatsApp / LinkedIn  ──────→  Needs_Action/social/  →  Local handles

                              Pending_Approvals/     ←  Human reviews in Obsidian
                              Approved/              →  Local executes via MCP
                              Done/ + audit.jsonl    ←  Everything logged
```

---

## Quick Start

**Requirements:** Python 3.13, [uv](https://docs.astral.sh/uv/)

```bash
# 1. Clone and install dependencies
git clone https://github.com/ZainabAlShahda/ai_employee.git
cd ai_employee
uv sync

# 2. Configure secrets
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY at minimum

# 3. Gmail OAuth (one-time — opens browser consent screen)
uv run python -c "from gmail_watcher import get_service; get_service()"

# 4. Start everything
uv run python health/monitor.py
```

`health/monitor.py` is the single entry point. It starts and auto-restarts:
- `agent/orchestrator.py` — Claude agent loop
- `filesystem_watcher.py` — watches `E:\AI_Dropbox`
- `gmail_watcher.py` — polls Gmail every 30 s
- `health/heartbeat.py` — writes liveness file every 30 s
- `sync/vault_sync.py` — git pull/push every 60 s
- `sync/dashboard_merger.py` — merges Updates → Dashboard.md

---

## Project Structure

```
ai_employee/
│
├── agent/                      Claude reasoning loop
│   ├── orchestrator.py         Domain-aware vault scanner + task dispatcher
│   ├── ralph_loop.py           Max-10-turn Claude agent loop
│   ├── skills.py               13 callable tools (email, social, finance, files)
│   └── prompts.py              System prompts for Cloud and Local modes
│
├── agent_platform/             Agent identity & capability management
│   ├── config.py               AgentConfig singleton — reads AGENT_MODE from .env
│   └── capabilities.py         Cloud vs Local allowed skills + draft-only gate
│
├── mcp_servers/                External action servers (Model Context Protocol)
│   ├── gmail_mcp.py            send_email · reply_email · label_email
│   ├── odoo_mcp.py             create_invoice · list_contacts · get_accounting_report · post_payment
│   └── social_mcp.py           post_linkedin · post_facebook · post_instagram · post_twitter
│
├── watchers/                   Social media input watchers
│   ├── facebook_watcher.py     Meta Graph API polling (60 s)
│   ├── instagram_watcher.py    Meta Graph API polling (60 s)
│   └── twitter_watcher.py      Tweepy API v2 + Playwright fallback
│
├── sync/                       Vault synchronisation
│   ├── vault_sync.py           git pull / commit / push loop
│   └── dashboard_merger.py     Merges Updates/*.md → Dashboard.md (Local only)
│
├── health/                     Process health management
│   ├── monitor.py              Subprocess watchdog — restarts dead processes
│   └── heartbeat.py            Writes Logs/heartbeat.json every HEARTBEAT_INTERVAL s
│
├── scheduler/
│   └── weekly_briefing.py      Generates CEO briefing every Monday at 08:45
│
├── audit/
│   └── logger.py               Structured JSONL logger → AI_Employee_Vault/Logs/audit.jsonl
│
├── deploy/                     Cloud deployment (Docker)
│   ├── docker-compose.yml      Odoo 17 + PostgreSQL 16 + agent container
│   ├── Dockerfile.agent        Python 3.13-slim image with uv
│   ├── supervisord.conf        Non-Docker fallback process manager
│   └── setup_cloud.sh          One-shot cloud VM bootstrap script
│
├── filesystem_watcher.py       Watches E:\AI_Dropbox → Needs_Action/files/
├── gmail_watcher.py            Gmail API polling → Needs_Action/email/
├── whatsapp_watcher.py         WhatsApp Web via Playwright (Local only)
├── linkedin_watcher.py         LinkedIn notifications via Playwright (Local only)
│
└── AI_Employee_Vault/          Obsidian vault — sole communication bus between agents
    ├── Needs_Action/           Incoming tasks
    │   ├── email/              Gmail watcher drops here — Cloud picks up
    │   ├── social/             Social watchers drop here — Cloud picks up
    │   ├── finance/            Payment / invoice items — Local picks up
    │   └── files/              Filesystem watcher drops here — Local picks up
    ├── In_Progress/
    │   ├── cloud/              Cloud claims here (claim-by-move)
    │   └── local/              Local claims here (claim-by-move)
    ├── Pending_Approvals/      Awaiting human sign-off
    ├── Approved/               Human-approved — Local executes
    ├── Done/                   Completed tasks
    ├── Rejected/               Failed after 3 retries
    ├── Plans/                  Task plans written by ralph_loop
    ├── Logs/                   audit.jsonl + heartbeat.json
    ├── Updates/                Cloud dashboard snippets
    ├── Dashboard.md            Live status overview (single-writer: Local)
    └── Company_Handbook.md     Operating rules and finance thresholds
```

---

## Configuration

Copy `.env.example` → `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for the agent loop and CEO briefing |
| `AGENT_MODE` | Yes | `local` or `cloud` (default: `local`) |
| `VAULT_PATH` | Yes | Absolute path to `AI_Employee_Vault/` |
| `VAULT_GIT_PATH` | Yes | Path to vault git repo (usually same as `VAULT_PATH`) |
| `GIT_VAULT_REMOTE` | Platinum | Git remote URL for vault sync — leave blank for single-machine |
| `ODOO_URL` | Odoo | Default: `http://localhost:8069` |
| `ODOO_DB` | Odoo | Odoo database name |
| `ODOO_USERNAME` | Odoo | Odoo login email |
| `ODOO_PASSWORD` | Odoo | Odoo password |
| `META_ACCESS_TOKEN` | Social | Meta Graph API token (Facebook + Instagram) |
| `META_PAGE_ID` | Social | Facebook Page ID |
| `META_IG_ACCOUNT_ID` | Social | Instagram Business account ID |
| `TWITTER_BEARER_TOKEN` | Social | Twitter/X bearer token |
| `TWITTER_API_KEY` | Social | Twitter/X API key |
| `TWITTER_API_SECRET` | Social | Twitter/X API secret |
| `TWITTER_ACCESS_TOKEN` | Social | Twitter/X access token |
| `TWITTER_ACCESS_SECRET` | Social | Twitter/X access secret |
| `SYNC_INTERVAL` | Platinum | Vault git sync interval in seconds (default: 60) |
| `HEARTBEAT_INTERVAL` | Platinum | Heartbeat write interval in seconds (default: 30) |
| `GIT_AGENT_REMOTE` | Cloud | Git remote for agent code repo (cloud bootstrap) |

---

## Authentication Setup

### Gmail (required for email watcher + MCP)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a project → enable Gmail API
2. Download OAuth 2.0 credentials → save as `credentials.json` in the project root
3. Run the one-time consent flow:
```bash
uv run python -c "from gmail_watcher import get_service; get_service()"
```
A browser window opens — approve access. `token.json` is saved automatically (gitignored).

### WhatsApp (Local only)
```bash
uv run python whatsapp_watcher.py
# A headed Chromium window opens — scan the QR code with your phone
```
Session state saves to `playwright_state/` (gitignored). Must be re-scanned when session expires.

### LinkedIn (Local only)
```bash
uv run python linkedin_watcher.py
# A headed Chromium window opens — log in manually
```

### Facebook + Instagram
Set `META_ACCESS_TOKEN`, `META_PAGE_ID`, and `META_IG_ACCOUNT_ID` in `.env`.
Get your token from [Meta for Developers](https://developers.facebook.com/).

### Twitter / X
Set all 5 `TWITTER_*` variables in `.env`.
Get credentials from [developer.twitter.com](https://developer.twitter.com/).

### Odoo
1. Install Odoo 17 Community locally or use the Docker stack (see [Cloud Deployment](#cloud-deployment-docker))
2. Set `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD` in `.env`
3. Odoo MCP communicates via JSON-RPC at `POST /web/session/authenticate`

---

## Running

### Option A — All-in-one (recommended)

```bash
uv run python health/monitor.py
```

Starts all components and auto-restarts any that crash.

### Option B — Individual components

```bash
uv run python agent/orchestrator.py         # Claude agent loop only
uv run python filesystem_watcher.py         # watch E:\AI_Dropbox for new files
uv run python gmail_watcher.py              # poll Gmail inbox every 30 s
uv run python sync/vault_sync.py            # git sync loop (requires GIT_VAULT_REMOTE)
uv run python health/heartbeat.py           # write heartbeat.json
uv run python scheduler/weekly_briefing.py  # generate CEO briefing immediately
```

### MCP servers (run separately when needed)

```bash
uv run python mcp_servers/gmail_mcp.py
uv run python mcp_servers/odoo_mcp.py
uv run python mcp_servers/social_mcp.py
```

---

## Cloud Deployment (Docker)

The `deploy/` directory contains a full Docker Compose stack:

```
Odoo 17 Community
PostgreSQL 16
Agent container (Python 3.13 + uv)
```

### Bootstrap a cloud VM

```bash
# On a fresh Ubuntu/Debian VM:
bash deploy/setup_cloud.sh
```

### Start the stack

```bash
cd /app
docker compose -f deploy/docker-compose.yml up -d

# View logs
docker compose -f deploy/docker-compose.yml logs -f agent
```

Set `AGENT_MODE=cloud` in the cloud `.env` and `AGENT_MODE=local` on your local machine.

---

## Platinum Two-Agent Flow

When both Cloud and Local are running with a shared `GIT_VAULT_REMOTE`:

```
[Cloud VM — always on]
  New email arrives
    → Gmail watcher writes Needs_Action/email/GMAIL_<id>.md
    → Orchestrator claims it (moves to In_Progress/cloud/)
    → ralph_loop drafts reply (max 10 Claude turns)
    → SEND_APPROVAL_<id>.md written to Pending_Approvals/
    → vault_sync commits + pushes to git

[Local machine — user returns]
  vault_sync pulls latest
    → User opens Obsidian, reviews SEND_APPROVAL file
    → User moves file to Approved/
    → Orchestrator picks up Approved/SEND_APPROVAL_<id>.md
    → _execute_send_approval() calls Gmail MCP → sends email
    → Task logged to audit.jsonl → moved to Done/
```

Approval files embed the intended action as HTML comments:
```markdown
<!-- platinum:tool:reply_email -->
<!-- platinum:inputs:{"message_id": "abc123", "body": "Dear ..."} -->
```

The claim-by-move rule ensures only one agent processes any given item — whichever agent moves it from `Needs_Action/` to `In_Progress/<agent_id>/` first owns it.

---

## Agent Skills (13 tools)

| Tool | MCP Server | Cloud | Local |
|---|---|---|---|
| `write_plan` | — | Yes | Yes |
| `request_approval` | — | Yes | Yes |
| `label_email` | gmail_mcp | Yes | Yes |
| `get_accounting_report` | odoo_mcp | Yes | Yes |
| `list_contacts` | odoo_mcp | Yes | Yes |
| `send_email` | gmail_mcp | Draft only | Yes |
| `reply_email` | gmail_mcp | Draft only | Yes |
| `post_linkedin` | social_mcp | Draft only | Yes |
| `post_facebook` | social_mcp | Draft only | Yes |
| `post_instagram` | social_mcp | Draft only | Yes |
| `post_twitter` | social_mcp | Draft only | Yes |
| `create_invoice` | odoo_mcp | Draft only | Yes |
| `post_payment` | odoo_mcp | Draft only | Yes |

"Draft only" = Cloud intercepts these and routes to `Pending_Approvals/` instead of executing.

---

## Security Model

Cloud is **never** allowed to execute send/post/payment actions directly. Two enforcement layers:

1. **ralph_loop.py** — intercepts any Claude attempt to call a `SEND_TOOL` and routes it to `request_approval` instead, writing a `SEND_APPROVAL_*.md` file
2. **skills.py `call_skill()`** — raises a hard error if `DRAFT_ONLY_MODE` is True and a `SEND_TOOL` is called, regardless of how the call arrived

**Finance rule:** any transaction > $500 routes to `Pending_Approvals/` unconditionally — enforced in both the system prompt and the skill layer.

**Secrets never sync:** `.env`, `credentials.json`, `token.json`, and session files are gitignored and never committed to the vault remote.

---

## Weekly CEO Briefing

Generated automatically every Monday at 08:45 (configure via Windows Task Scheduler).

Run on demand:
```bash
uv run python scheduler/weekly_briefing.py
```

Output: `AI_Employee_Vault/Plans/CEO_Briefing_YYYY-MM-DD.md`

Contents:
- Odoo Profit & Loss from last week (`get_accounting_report`)
- Vault task counts: Done / Approved / Rejected / Pending
- Last 7 days of `audit.jsonl` summarised
- Claude-written narrative (claude-opus-4-6)

---

## Vault Folder Reference

| Folder | Written by | Read / acted on by |
|---|---|---|
| `Needs_Action/email/` | Gmail watcher | Cloud orchestrator |
| `Needs_Action/social/` | Social watchers | Cloud orchestrator |
| `Needs_Action/finance/` | Manual / invoices | Local orchestrator |
| `Needs_Action/files/` | Filesystem watcher | Local orchestrator |
| `In_Progress/cloud/` | Cloud (claim-by-move) | Cloud |
| `In_Progress/local/` | Local (claim-by-move) | Local |
| `Pending_Approvals/` | Cloud ralph_loop | Human (Obsidian) |
| `Approved/` | Human | Local orchestrator |
| `Done/` | Local orchestrator | — |
| `Rejected/` | Either orchestrator | Human review |
| `Plans/` | ralph_loop | — |
| `Logs/` | heartbeat + audit logger | Monitoring / briefing |
| `Updates/` | Cloud | dashboard_merger (Local) |

---

## Audit Logging

Every action is appended to `AI_Employee_Vault/Logs/audit.jsonl` as a structured JSON line:

```json
{"ts": "2026-02-26T01:36:27Z", "task": "GMAIL_abc123.md", "action": "send_email", "input": {...}, "result": {"ok": true}, "agent_turn": 3}
```

Fields: `ts` · `task` · `action` · `input` · `result` · `agent_turn`

---

## Company Operating Rules

Defined in `AI_Employee_Vault/Company_Handbook.md`:

- Transactions **> $500** → route to `Pending_Approvals/` (never execute directly)
- Transactions **≤ $500** → route to `Approved/` and log
- All actions must be logged in `Logs/`
- Completed tasks move to `Done/`
- No external cloud storage unless explicitly approved — all data stays in the vault

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | Claude API (agent loop + CEO briefing) |
| `fastmcp` | MCP server framework |
| `google-api-python-client` | Gmail API |
| `google-auth-oauthlib` | Gmail OAuth2 flow |
| `playwright` | WhatsApp + LinkedIn browser automation |
| `tweepy` | Twitter/X API v2 |
| `requests` | Meta Graph API + Odoo JSON-RPC |
| `watchdog` | Filesystem events (AI_Dropbox watcher) |
| `python-dotenv` | `.env` file loading |
| `schedule` | CEO briefing weekly scheduler |

Install all: `uv sync`

---

## License

Private project. All rights reserved.
