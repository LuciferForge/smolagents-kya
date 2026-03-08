"""Card helpers — create and manage KYA identity cards for smolagents agents.

Works with or without smolagents installed. When smolagents is available, cards
are stored on agent objects via a _kya_card attribute.

smolagents agents (CodeAgent, ToolCallingAgent) have:
- tools: list of Tool instances
- model: the LLM model
- system_prompt: the system prompt string
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional


def _resolve_agent_fields(agent: Any) -> Dict[str, str]:
    """Extract identity-relevant fields from a smolagents Agent object.

    smolagents agents have: tools, model, system_prompt.
    Unlike CrewAI, there's no explicit role/goal. We derive identity from
    the class name and system_prompt.
    """
    # Agent class name as the role
    class_name = type(agent).__name__
    system_prompt = getattr(agent, "system_prompt", "") or ""

    # Build a stable slug from the class name
    slug = class_name.lower().replace(" ", "-").replace("_", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    slug = slug.strip("-") or "agent"

    # Extract model name if available
    model = getattr(agent, "model", None)
    model_name = ""
    if model is not None:
        model_name = getattr(model, "model_id", "") or getattr(model, "model_name", "") or type(model).__name__

    return {
        "class_name": class_name,
        "system_prompt": system_prompt,
        "slug": slug,
        "model_name": model_name,
    }


def _extract_tool_capabilities(agent: Any) -> List[Dict[str, str]]:
    """Extract capabilities from a smolagents agent's tools list.

    smolagents Tool has: name, description, inputs, output_type.
    """
    tools = getattr(agent, "tools", None) or []
    # smolagents stores tools as a dict {name: tool} or a list
    if isinstance(tools, dict):
        tools = list(tools.values())

    capabilities = []
    for tool in tools:
        name = getattr(tool, "name", None) or type(tool).__name__
        description = getattr(tool, "description", "") or ""
        capabilities.append({
            "name": name,
            "description": description[:200],
            "risk_level": "medium",  # Conservative default
            "scope": "as-configured",
        })
    return capabilities


def create_agent_card(
    agent: Any,
    *,
    owner_name: str = "unspecified",
    owner_contact: str = "unspecified",
    agent_id_prefix: str = "smolagents",
    name: Optional[str] = None,
    purpose: Optional[str] = None,
    capabilities: Optional[List[Dict[str, str]]] = None,
    version: str = "0.1.0",
    risk_classification: str = "minimal",
    human_oversight: str = "human-on-the-loop",
) -> Dict[str, Any]:
    """Create a KYA identity card from a smolagents Agent.

    Args:
        agent: A smolagents CodeAgent/ToolCallingAgent instance (or compatible).
        owner_name: Organization or person responsible for this agent.
        owner_contact: Contact email for security/compliance inquiries.
        agent_id_prefix: Prefix for the agent_id (default: "smolagents").
        name: Override agent name. If None, derived from class name.
        purpose: Override purpose text. If None, derived from system_prompt.
        capabilities: Override auto-detected capabilities. If None, extracted from agent.tools.
        version: Semantic version for the agent.
        risk_classification: EU AI Act risk level (minimal/limited/high/unacceptable).
        human_oversight: Oversight level (none/human-on-the-loop/human-in-the-loop/human-above-the-loop).

    Returns:
        A KYA card dict conforming to the v0.1 schema.
    """
    fields = _resolve_agent_fields(agent)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if capabilities is None:
        capabilities = _extract_tool_capabilities(agent)

    # Determine agent name
    agent_name = name or fields["class_name"]

    # Build purpose from system_prompt or explicit override
    if purpose is None:
        sp = fields["system_prompt"]
        if sp and len(sp) >= 10:
            # Take first 500 chars of system prompt as purpose
            purpose = sp[:500]
        else:
            purpose = f"smolagents {fields['class_name']} agent"
    # Ensure purpose meets KYA minLength of 10
    if len(purpose) < 10:
        purpose = f"smolagents agent running as {fields['class_name']}"
    # Cap at schema maxLength
    purpose = purpose[:500]

    # Determine agent type based on class
    agent_type = "autonomous"

    card: Dict[str, Any] = {
        "kya_version": "0.1",
        "agent_id": f"{agent_id_prefix}/{fields['slug']}",
        "name": agent_name,
        "version": version,
        "purpose": purpose,
        "agent_type": agent_type,
        "owner": {
            "name": owner_name,
            "contact": owner_contact,
        },
        "capabilities": {
            "declared": capabilities,
            "denied": [],
        },
        "data_access": {
            "sources": [],
            "destinations": [],
            "pii_handling": "none",
            "retention_policy": "session-only",
        },
        "security": {
            "last_audit": None,
            "known_vulnerabilities": [],
            "injection_tested": False,
        },
        "compliance": {
            "frameworks": [],
            "risk_classification": risk_classification,
            "human_oversight": human_oversight,
        },
        "behavior": {
            "logging_enabled": False,
            "log_format": "none",
            "max_actions_per_minute": 0,
            "kill_switch": True,
            "escalation_policy": "halt-and-notify",
        },
        "metadata": {
            "created_at": now,
            "updated_at": now,
            "tags": ["smolagents"],
        },
    }

    # Add model info if available
    if fields["model_name"]:
        card["metadata"]["model"] = fields["model_name"]

    return card


def attach_card(agent: Any, card: Dict[str, Any]) -> None:
    """Attach a KYA identity card to a smolagents Agent instance.

    Stores the card as agent._kya_card for retrieval by tools and middleware.
    """
    agent._kya_card = card


def get_card(agent: Any) -> Optional[Dict[str, Any]]:
    """Retrieve the KYA card attached to a smolagents Agent, if any."""
    return getattr(agent, "_kya_card", None)
