"""
platform/capabilities.py — Per-mode allowed skills and draft-only flag.

Cloud gets read/draft/plan tools only.
Local gets all 13 skills (full access).

Send/post tools that Cloud must intercept and route to Pending_Approvals:
"""

from __future__ import annotations

from platform.config import agent_config

# Tools that directly act on the outside world — Cloud must NOT call these;
# it must route them through request_approval instead.
SEND_TOOLS: frozenset[str] = frozenset({
    "send_email",
    "reply_email",
    "post_linkedin",
    "post_facebook",
    "post_instagram",
    "post_twitter",
    "post_payment",
    "create_invoice",
})

# Tools available to Cloud (read + draft + plan)
CLOUD_SKILLS: frozenset[str] = frozenset({
    "write_plan",
    "request_approval",
    "label_email",
    "get_accounting_report",
    "list_contacts",
})

# Flag: True when running in cloud (draft-only) mode
DRAFT_ONLY_MODE: bool = (agent_config.mode == "cloud")


def get_allowed_skills() -> set[str]:
    """Return the set of skill names permitted for the current agent mode."""
    if agent_config.mode == "cloud":
        return set(CLOUD_SKILLS)
    # Local: import full registry lazily to avoid circular imports
    from agent.skills import SKILL_REGISTRY  # noqa: PLC0415
    return set(SKILL_REGISTRY.keys())


def get_tool_schemas() -> list[dict]:
    """Return tool schemas filtered to those allowed in the current mode."""
    from agent.skills import TOOL_SCHEMAS  # noqa: PLC0415
    allowed = get_allowed_skills()
    return [t for t in TOOL_SCHEMAS if t["name"] in allowed]
