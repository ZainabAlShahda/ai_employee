# AI Employee — Platinum Tier

An always-on autonomous AI system that monitors email, social media, and files; drafts responses; manages Odoo accounting; and executes approved actions — all while keeping a human in the loop for anything sensitive.

Two cooperating agents (Cloud + Local) share state exclusively through a Git-synced Obsidian vault. Cloud runs 24/7 and drafts actions. Local owns all final sends, payments, and approvals.

---

## How It Works

```
[Inputs]                        [Vault]                      [Outputs]
Gmail ──────────────────→  Needs_Action/email/   →  Cloud drafts reply
Facebook/Instagram/X ──→  Needs_Action/social/  →  Cloud drafts post
File Drop (AI_Dropbox) →  Needs_Action/files/   →  Local processes
WhatsApp / LinkedIn ───→  Needs_Action/social/  →  Local handles

                         Pending_Approvals/      ←  Human reviews in Obsidian
                         Approved/               →  Local executes via MCP
                         Done/ + audit.jsonl     ←  Everything logged
```

---

## Quick Start (Local Mode)

**Requirements:** Python 3.13, [uv](https://docs.astral.sh/uv/)

```bash
# 1. Clone and install
git clone https://github.com/ZainabAlShahda/ai_employee.git
cd ai_employee
uv sync

# 2. Configure secrets
cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY at minimum

# 3. Gmail OAuth (one-time, opens browser)
uv run python -c "from gmail_watcher import get_service; get_service()"

# 4. Start everything
uv run python health/monitor.py
```

The monitor starts the orchestrator, filesystem watcher, Gmail watcher, heartbeat, and vault sync — and auto-restarts any that crash.

---

## Project Structure

```
ai_employee/
├── agent/                  Claude reasoning loop
│   ├── orchestrator.py     Scans vault, claims tasks, runs ralph_loop
│   ├── ralph_loop.py       Max-10-turn Claude agent loop
│   ├── skills.py           13 tool callables (email, social, finance, files)
│   └── prompts.py          System prompts for cloud and local modes
│
├── agent_platform/         Agent identity & capability management
│   ├── config.py           AgentConfig — reads AGENT_MODE from .env
│   └── capabilities.py     Cloud vs Local skill sets + draft-only gate
│
├── mcp_servers/            External action servers
│   ├── gmail_mcp.py        send_email, reply_email, label_email
│   ├── odoo_mcp.py         create_invoice, list_contacts, get_accounting_report, post_payment
│   └── social_mcp.py       post_linkedin, post_facebook, post_instagram, post_twitter
│
├── watchers/               Social media input watchers
│   ├── facebook_watcher.py Meta Graph API polling (60s)
│   ├── instagram_watcher.py Meta Graph API polling (60s)
│   └── twitter_watcher.py  Tweepy v2 + Playwright fallback
│
├── sync/                   Vault synchronisation
│   ├── vault_sync.py       git pull/commit/push loop + secret scan
│   └── dashboard_merger.py Merges Updates/*.md → Dashboard.md
│
├── health/                 Process health
│   ├── monitor.py          Subprocess watchdog — restarts dead processes
│   └── heartbeat.py        Writes Logs/heartbeat.json every 30s
│
├── scheduler/
│   └── weekly_briefing.py  Auto-generates CEO briefing every Monday
│
├── audit/
│   └── logger.py           Structured JSONL logger → Logs/audit.jsonl
│
├── deploy/                 Cloud deployment (Docker)
│   ├── docker-compose.yml  Odoo 17 + PostgreSQL + Caddy + backup + agent
│   ├── Caddyfile           Auto-TLS reverse proxy for Odoo
│   ├── Dockerfile.agent    Python 3.13-slim container
│   ├── setup_cloud.sh      One-shot VM bootstrap script
│   └── backups/            pg_dump daily output (gitkeep, .sql excluded)
│
├── docs/
│   └── lessons_learned.md  Design decisions and trade-offs
│
├── filesystem_watcher.py   Watches E:\AI_Dropbox → Needs_Action/
├── gmail_watcher.py        Gmail API polling → Needs_Action/email/
├── whatsapp_watcher.py     WhatsApp Web (Playwright, Local only)
├── linkedin_watcher.py     LinkedIn notifications (Playwright, Local only)
│
└── AI_Employee_Vault/      Obsidian vault — sole state bus between agents
    ├── Needs_Action/        Incoming tasks (email/, social/, finance/, files/)
    ├── In_Progress/         Claimed tasks (cloud/, local/)
    ├── Pending_Approvals/   Awaiting human sign-off
    ├── Approved/            Human-approved — Local executes
    ├── Done/                Completed tasks
    ├── Rejected/            Failed after 3 retries
    ├── Plans/               Task plans written by ralph_loop
    ├── Logs/                audit.jsonl + heartbeat.json
    ├── Updates/             Cloud dashboard snippets
    ├── Dashboard.md         Live status (single-writer: Local)
    └── Company_Handbook.md  Operating rules
```

---

## Configuration (`.env`)

Copy `.env.example` to `.env` and fill in values:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API — required for agent loop |
| `AGENT_MODE` | `local` or `cloud` (default: `local`) |
| `VAULT_PATH` | Path to `AI_Employee_Vault/` |
| `VAULT_GIT_PATH` | Path to vault git repo (same as above unless separate) |
| `GIT_VAULT_REMOTE` | Git remote for vault sync (leave blank for single-machine) |
| `ODOO_URL` | Odoo instance URL (default: `http://localhost:8069`) |
| `ODOO_DB` | Odoo database name |
| `ODOO_USERNAME` | Odoo login |
| `ODOO_PASSWORD` | Odoo password |
| `ODOO_DOMAIN` | Domain for Caddy HTTPS / Let's Encrypt |
| `META_ACCESS_TOKEN` | Meta Graph API token (Facebook + Instagram) |
| `META_PAGE_ID` | Facebook Page ID |
| `META_IG_ACCOUNT_ID` | Instagram Business account ID |
| `TWITTER_*` | 5 Tweepy OAuth1 tokens for X/Twitter |
| `SYNC_INTERVAL` | Vault sync interval in seconds (default: 60) |
| `HEARTBEAT_INTERVAL` | Heartbeat write interval in seconds (default: 30) |

---

## Authentication Setup

### Gmail
```bash
# Place credentials.json (Google OAuth client) in the project root
# Run once to complete browser consent — saves token.json
uv run python -c "from gmail_watcher import get_service; get_service()"
```

### WhatsApp / LinkedIn
These use Playwright (headed browser) and require manual login per session. Run them directly — they are **Local only** and not started by the monitor:
```bash
uv run python whatsapp_watcher.py   # scan QR code when browser opens
uv run python linkedin_watcher.py   # log in manually when browser opens
```

### Odoo
1. Use the Docker stack (`deploy/docker-compose.yml`) or install Odoo 17 Community locally
2. Set `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD` in `.env`

---

## Running

### Local mode (recommended starting point)

```bash
uv run python health/monitor.py
```

Starts: orchestrator · filesystem watcher · Gmail watcher · heartbeat · vault sync · dashboard merger

### Individual components

```bash
uv run python agent/orchestrator.py         # agent loop only
uv run python filesystem_watcher.py         # watch E:\AI_Dropbox
uv run python gmail_watcher.py              # watch Gmail inbox
uv run python sync/vault_sync.py            # git sync loop
uv run python scheduler/weekly_briefing.py  # generate CEO briefing now
```

### MCP servers (run separately if needed)

```bash
uv run python mcp_servers/gmail_mcp.py
uv run python mcp_servers/odoo_mcp.py
uv run python mcp_servers/social_mcp.py
```

### Cloud mode (Docker — full Platinum)

```bash
# On the cloud VM after running deploy/setup_cloud.sh:
cd /app
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml logs -f agent
```

Set in cloud `.env`: `AGENT_MODE=cloud` and `GIT_VAULT_REMOTE=<ssh-url>`
Set in local `.env`: `AGENT_MODE=local` and `GIT_VAULT_REMOTE=<ssh-url>`

---

## Platinum Two-Agent Flow

```
[Cloud VM — always on]
  Email/social arrives → orchestrator claims → ralph_loop drafts reply
  → SEND_APPROVAL_*.md written to Pending_Approvals/
  → vault_sync pushes to git

[Local machine — user returns]
  vault_sync pulls → user opens Obsidian → reviews SEND_APPROVAL file
  → moves to Approved/ → orchestrator picks up → executes via MCP
  → logs to audit.jsonl → moves to Done/
```

Approval files embed the intended action as metadata:
```markdown
<!-- platinum:tool:reply_email -->
<!-- platinum:inputs:{"message_id": "...", "body": "..."} -->
```

---

## Security

Three independent layers prevent secrets from syncing to the vault remote:

1. **`AI_Employee_Vault/.gitignore`** — blocks `.env`, `credentials.json`, `*.key`, `*.pem`, etc.
2. **Pre-push scan** (`sync/vault_sync.py`) — aborts commit if any secret file is staged
3. **Capability gate** (`agent_platform/capabilities.py`) — Cloud never holds payment tokens or session credentials; `SEND_TOOLS` are hard-blocked in cloud mode

Cloud agent **cannot** send emails, post to social, or make payments — it can only draft and request approval. Local agent executes after human review.

**Finance rule:** transactions > $500 always route to `Pending_Approvals/` regardless of agent mode.

---

## Vault Folder Reference

| Folder | Written by | Read by |
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
| `Logs/` | heartbeat + audit | Monitoring |
| `Updates/` | Cloud | dashboard_merger (Local) |

---

## Weekly CEO Briefing

Auto-generated every Monday at 08:45 (configure via Windows Task Scheduler):

```bash
uv run python scheduler/weekly_briefing.py
```

Output: `AI_Employee_Vault/Plans/CEO_Briefing_<date>.md`

Includes: Odoo P&L · vault task counts · 7-day audit summary · Claude narrative

---

## Dependencies

Key packages (see `pyproject.toml` for full list):

- `anthropic` — Claude API
- `fastmcp` — MCP server framework
- `google-api-python-client` + `google-auth-oauthlib` — Gmail
- `playwright` — WhatsApp / LinkedIn browser automation
- `tweepy` — Twitter/X API
- `requests` — Meta Graph API, Odoo JSON-RPC
- `watchdog` — filesystem events
- `python-dotenv` — `.env` loading
- `schedule` — CEO briefing scheduler

---

## License

Private project. All rights reserved.
