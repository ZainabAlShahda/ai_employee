# Lessons Learned — AI Employee Project

Gold Tier requirement #11: document key design decisions, trade-offs, and hard-won insights
from building and operating the AI Employee system through Silver → Gold → Platinum tiers.

---

## 1. Claim-by-Move vs. a Task Queue

**Decision:** use filesystem rename (move from `Needs_Action/` → `In_Progress/<agent_id>/`) as the
exclusive claim mechanism rather than a database or broker queue.

**Why it worked:**
- Zero extra infrastructure — no Redis, no SQLite, no message bus.
- The vault *is* the queue. Human operators can inspect, edit, or manually move files in Obsidian
  without touching any code.
- Atomic on most local filesystems (POSIX `rename(2)`). Race conditions between Cloud and Local
  are resolved by git merge ordering; the worst outcome is a duplicate attempt, not data loss.

**Trade-off:** does not scale to hundreds of concurrent items or sub-second latency. That is fine
for an "AI Employee" workload where items arrive in ones and twos.

---

## 2. Git vs. Syncthing for Vault Synchronisation

**Decision:** git push/pull loop (`sync/vault_sync.py`) rather than real-time sync tools like
Syncthing or Dropbox.

**Why git:**
- Full audit trail — every state transition (Needs_Action → In_Progress → Done) is a commit.
  Disputes can be resolved by reading `git log`.
- Branching and conflict resolution are well-understood. Rebase-on-pull avoids extraneous merge
  commits.
- Works over SSH from any cloud VM without installing additional agents.
- Secret exclusion is enforced at the git layer (`.gitignore` + pre-push hook in
  `vault_sync.py`), not by trusting the sync tool's filters.

**Trade-off:** latency. Changes take up to `SYNC_INTERVAL` seconds (default 60 s) to propagate.
For an approval workflow this is fine. For real-time chat it would not be.

---

## 3. Two-Layer Draft-Only Gate

**Decision:** enforce Cloud's draft-only constraint in *two* independent places:

1. **ralph_loop.py** — intercepts `SEND_TOOLS` at the Claude response level before any skill is
   called. Routes to `request_approval` instead.
2. **skills.py `call_skill()`** — unconditionally raises if `DRAFT_ONLY_MODE` is True and a
   `SEND_TOOL` is requested, regardless of how the call arrived.

**Why two layers:** defence in depth. A prompt-injection attack or a future code change that
modifies the loop logic should not be the sole protection against unintended sends.

**Lesson:** "belt and suspenders" at module boundaries costs almost nothing and prevents entire
classes of bugs.

---

## 4. $500 Payment Gate Design

**Decision:** route any transaction > $500 to `Pending_Approvals/` unconditionally. Enforce this
in *both* the system prompt and the skill layer.

**Why both:**
- The prompt rule informs the model so it generates appropriate reasoning and approval files.
- The skill-layer check (`post_payment` guard in `skills.py`) is the authoritative enforcement.
  If the model ignores the prompt, the skill still refuses.

**Lesson:** never rely solely on language model compliance for financial controls. Always add a
hard code path that does not trust the model's judgement.

---

## 5. Caddy vs. nginx for HTTPS

**Decision:** use Caddy as the HTTPS reverse proxy in front of Odoo rather than nginx.

**Why Caddy:**
- Automatic ACME / Let's Encrypt certificate provisioning with zero configuration beyond the
  domain name. With nginx you manage cert renewal via certbot cron.
- A single `{$ODOO_DOMAIN} { reverse_proxy odoo:8069 }` stanza is the entire TLS configuration.
- Caddy 2 ships as a single static binary; no Lua, no modules to compile.

**Trade-off:** Caddy is less widely documented than nginx for advanced use cases (WAF, rate
limiting). For a single-backend proxy serving one domain it is the simpler choice.

---

## 6. Ralph Loop: Max-Turns Safety Valve

**Decision:** hard-cap the Claude reasoning loop at 10 turns (`MAX_TURNS = 10`).

**Why:**
- Without a cap, a misbehaving or confused model can loop indefinitely on an ambiguous task,
  burning API budget and blocking the orchestrator thread.
- 10 turns is enough for: read item → write plan → call 2–3 tools → write Done summary. Real
  tasks rarely exceed 6 turns.
- Hitting the cap moves the item to `Rejected/` with a `max_turns_exceeded` reason, making the
  failure visible without human intervention.

**Lesson:** always bound autonomous loops. The cost of a premature stop is a human review; the
cost of an infinite loop is much higher.

---

## 7. File-Based A2A vs. Network A2A

**Decision (current):** agents communicate via vault files (file-based Agent-to-Agent).

**Why for now:**
- No extra network surface to secure between Cloud and Local.
- The vault file is the approval document — it is human-readable and editable in Obsidian.
- Rollout risk is minimal: if the sync breaks, agents simply stop passing work until git is fixed.

**Upgrade path (Platinum Phase 2):** replace file handoffs with direct A2A protocol messages
while keeping the vault as an audit record. The current design keeps the vault as the *only* bus,
so swapping in A2A messaging requires only changes to `orchestrator.py` and `ralph_loop.py` —
the skill layer and MCP servers are unaffected.

---

## 8. WhatsApp Playwright Fragility

**Challenge:** `whatsapp_watcher.py` uses Playwright to automate WhatsApp Web. This is fragile:

- Sessions expire after a few days; the QR scan must be redone manually.
- WhatsApp Web detects headless Chromium and may block it; headed mode is required.
- WhatsApp ToS prohibit automation; the watcher is best-effort and for personal use only.

**Mitigations applied:**
- Session state is saved to `playwright_state/` (gitignored, never synced to vault).
- The watcher is **Local-only**: it is not included in Cloud's process list in `monitor.py`.
  Cloud cannot hold a WhatsApp session because headed Chromium cannot run in a container.
- Graceful degradation: if the watcher fails, items simply do not appear in
  `Needs_Action/social/`; the rest of the system is unaffected.

**Lesson:** isolate fragile, session-dependent integrations to Local mode. Design the system so
their failure is localised and non-blocking.

---

## 9. Vault `.gitignore` as Last-Resort Secret Guard

**Decision:** add a `.gitignore` inside `AI_Employee_Vault/` listing secret file patterns, in
addition to the root `.gitignore` and the pre-push scan in `vault_sync.py`.

**Why the redundancy:**
- The vault may eventually be managed as a *separate* git repo (common for Obsidian users who
  sync their vault independently). In that case the root `.gitignore` does not apply.
- Three independent layers (root ignore, vault ignore, pre-push scan) mean a secret would need
  to evade all three simultaneously — highly unlikely.

---

## 10. Orchestrator Thread Model

**Decision:** `ThreadPoolExecutor(max_workers=3)` in `orchestrator.py` rather than asyncio or
multiprocessing.

**Why:**
- Tasks are I/O-bound (waiting on Claude API, Gmail, Odoo). Threads are fine; GIL is not a
  bottleneck.
- Three workers cap concurrent API calls, preventing rate-limit exhaustion on free-tier keys.
- Simpler error handling than asyncio for a team unfamiliar with async Python.

**Lesson:** match concurrency primitives to actual workload characteristics. "Async all the
things" would add complexity without benefit here.
