"""Tests for smolagents-kya integration.

Tests work without smolagents installed by using mock agent/tool classes
that mirror the smolagents API surface.
"""

import json
import pytest
from typing import Any

from smolagents_kya.card import create_agent_card, attach_card, get_card
from smolagents_kya.identity import verify_identity, _verify_card_data
from smolagents_kya.trust_gate import evaluate_trust
from smolagents_kya.middleware import kya_verified, KYAVerificationError


# ── Mock smolagents classes ──


class Tool:
    """Mimics smolagents.Tool for testing."""

    name = ""
    description = ""
    inputs = {}
    output_type = "string"

    def __init__(self, name: str = "", description: str = ""):
        self.name = name
        self.description = description


class CodeAgent:
    """Mimics smolagents.CodeAgent for testing."""

    def __init__(self, tools=None, model=None, system_prompt=""):
        self.tools = tools or []
        self.model = model
        self.system_prompt = system_prompt


class ToolCallingAgent:
    """Mimics smolagents.ToolCallingAgent for testing."""

    def __init__(self, tools=None, model=None, system_prompt=""):
        self.tools = tools or []
        self.model = model
        self.system_prompt = system_prompt


class MockModel:
    """Mimics a smolagents model."""

    def __init__(self, model_id="test-model"):
        self.model_id = model_id


# ── Card creation ──


class TestCreateAgentCard:
    def test_basic_card_from_code_agent(self):
        agent = CodeAgent(system_prompt="Research and analyze scientific papers")
        card = create_agent_card(agent, owner_name="TestOrg", owner_contact="test@test.com")

        assert card["kya_version"] == "0.1"
        assert card["agent_id"] == "smolagents/codeagent"
        assert card["name"] == "CodeAgent"
        assert "Research and analyze scientific papers" in card["purpose"]
        assert card["owner"]["name"] == "TestOrg"
        assert card["owner"]["contact"] == "test@test.com"
        assert "smolagents" in card["metadata"]["tags"]

    def test_card_from_tool_calling_agent(self):
        agent = ToolCallingAgent(system_prompt="Manage customer support tickets")
        card = create_agent_card(agent)

        assert card["agent_id"] == "smolagents/toolcallingagent"
        assert card["name"] == "ToolCallingAgent"

    def test_card_with_tools(self):
        tools = [
            Tool("web_search", "Search the web for information"),
            Tool("file_read", "Read files from disk"),
        ]
        agent = CodeAgent(tools=tools, system_prompt="A helpful research agent")
        card = create_agent_card(agent, owner_name="Org")

        declared = card["capabilities"]["declared"]
        assert len(declared) == 2
        assert declared[0]["name"] == "web_search"
        assert declared[1]["name"] == "file_read"

    def test_card_with_tools_as_dict(self):
        """smolagents can store tools as {name: tool_instance} dict."""
        t1 = Tool("search", "Search")
        t2 = Tool("calc", "Calculate")
        agent = CodeAgent(system_prompt="Agent with dict tools")
        agent.tools = {"search": t1, "calc": t2}
        card = create_agent_card(agent)

        declared = card["capabilities"]["declared"]
        assert len(declared) == 2
        names = {c["name"] for c in declared}
        assert "search" in names
        assert "calc" in names

    def test_card_custom_prefix(self):
        agent = CodeAgent(system_prompt="A test agent for custom prefix")
        card = create_agent_card(agent, agent_id_prefix="myorg")
        assert card["agent_id"] == "myorg/codeagent"

    def test_card_custom_name_and_purpose(self):
        agent = CodeAgent(system_prompt="Default prompt")
        card = create_agent_card(
            agent,
            name="ResearchBot",
            purpose="Specialized bot for academic paper analysis",
        )
        assert card["name"] == "ResearchBot"
        assert card["purpose"] == "Specialized bot for academic paper analysis"

    def test_purpose_minimum_length(self):
        agent = CodeAgent(system_prompt="Hi")
        card = create_agent_card(agent)
        assert len(card["purpose"]) >= 10

    def test_card_has_metadata_timestamps(self):
        agent = CodeAgent(system_prompt="Timestamp test agent")
        card = create_agent_card(agent)
        assert card["metadata"]["created_at"] != ""
        assert card["metadata"]["updated_at"] != ""

    def test_card_captures_model_info(self):
        model = MockModel(model_id="Qwen/Qwen2.5-72B-Instruct")
        agent = CodeAgent(model=model, system_prompt="Agent with model info")
        card = create_agent_card(agent)
        assert card["metadata"]["model"] == "Qwen/Qwen2.5-72B-Instruct"

    def test_card_no_model(self):
        agent = CodeAgent(system_prompt="Agent without model")
        card = create_agent_card(agent)
        assert "model" not in card["metadata"]


# ── Card attachment ──


class TestAttachCard:
    def test_attach_and_get(self):
        agent = CodeAgent(system_prompt="Test attach")
        card = {"kya_version": "0.1", "agent_id": "test/test"}
        attach_card(agent, card)
        assert get_card(agent) == card

    def test_get_card_none_when_not_attached(self):
        agent = CodeAgent(system_prompt="Test no card")
        assert get_card(agent) is None


# ── Identity verification ──


VALID_CARD = {
    "kya_version": "0.1",
    "agent_id": "smolagents/codeagent",
    "name": "CodeAgent",
    "version": "0.1.0",
    "purpose": "A smolagents agent that researches topics and summarizes findings.",
    "agent_type": "autonomous",
    "owner": {"name": "TestOrg", "contact": "test@test.com"},
    "capabilities": {
        "declared": [
            {"name": "web_search", "risk_level": "medium"},
            {"name": "summarize", "risk_level": "low"},
        ],
        "denied": [],
    },
}

MINIMAL_CARD = {
    "kya_version": "0.1",
    "agent_id": "smolagents/minimal",
    "name": "Minimal",
    "version": "0.1.0",
    "purpose": "A minimal test agent for validation.",
    "owner": {"name": "Test", "contact": "test@test.com"},
    "capabilities": {"declared": [{"name": "test", "risk_level": "low"}]},
}

INVALID_CARD = {
    "kya_version": "0.1",
    "name": "Broken",
    # Missing agent_id, purpose, capabilities, owner
}


class TestIdentityVerification:
    def test_valid_card(self):
        result = verify_identity(json.dumps(VALID_CARD))
        assert "VERIFIED" in result
        assert "CodeAgent" in result

    def test_invalid_card(self):
        result = verify_identity(json.dumps(INVALID_CARD))
        assert "FAILED" in result

    def test_invalid_json(self):
        result = verify_identity("not json")
        assert "FAILED" in result
        assert "Invalid JSON" in result

    def test_verify_data_returns_capabilities(self):
        result = _verify_card_data(VALID_CARD)
        assert "web_search" in result["capabilities"]
        assert "summarize" in result["capabilities"]

    def test_verify_data_score(self):
        result = _verify_card_data(VALID_CARD)
        assert result["completeness_score"] > 0


# ── Trust gate ──


class TestTrustGate:
    def test_passes_valid_card(self):
        result = evaluate_trust(json.dumps(VALID_CARD), min_score=0)
        assert "PASSED" in result

    def test_blocks_low_score(self):
        result = evaluate_trust(json.dumps(MINIMAL_CARD), min_score=100)
        assert "BLOCKED" in result
        assert "below threshold" in result

    def test_blocks_missing_capabilities(self):
        result = evaluate_trust(
            json.dumps(VALID_CARD),
            min_score=0,
            required_capabilities="web_search,secret_power",
        )
        assert "BLOCKED" in result
        assert "secret_power" in result

    def test_blocks_unsigned_when_signature_required(self):
        result = evaluate_trust(
            json.dumps(VALID_CARD),
            min_score=0,
            require_signature=True,
        )
        assert "BLOCKED" in result
        assert "unsigned" in result.lower()

    def test_invalid_json(self):
        result = evaluate_trust("bad json")
        assert "BLOCKED" in result


# ── Middleware decorator ──


class TestKYAVerified:
    def test_passes_with_valid_card(self):
        agent = CodeAgent(
            tools=[Tool("research", "Research tool")],
            system_prompt="A research agent that finds and analyzes information",
        )
        card = create_agent_card(agent, owner_name="Test", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=0)
        def task(agent):
            return "executed"

        assert task(agent) == "executed"

    def test_raises_without_card(self):
        agent = CodeAgent(system_prompt="Naked agent with no card")

        @kya_verified()
        def task(agent):
            return "executed"

        with pytest.raises(KYAVerificationError, match="No KYA card"):
            task(agent)

    def test_raises_on_low_score(self):
        agent = CodeAgent(system_prompt="Weak agent with low completeness")
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=100)
        def task(agent):
            return "executed"

        with pytest.raises(KYAVerificationError, match="below required"):
            task(agent)

    def test_skip_on_fail(self):
        agent = CodeAgent(system_prompt="Skippable agent")

        @kya_verified(on_fail="skip")
        def task(agent):
            return "executed"

        assert task(agent) is None

    def test_log_on_fail(self, capsys):
        agent = CodeAgent(system_prompt="Logged agent for testing")

        @kya_verified(on_fail="log")
        def task(agent):
            return "executed"

        result = task(agent)
        assert result == "executed"
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_agent_as_kwarg(self):
        agent = CodeAgent(
            system_prompt="Kwarg agent for testing keyword argument passing",
        )
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=0)
        def task(data, agent=None):
            return f"processed {data}"

        assert task("stuff", agent=agent) == "processed stuff"

    def test_required_capabilities(self):
        agent = CodeAgent(
            tools=[Tool("reading", "Read documents")],
            system_prompt="Agent with reading capability for testing",
        )
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(required_capabilities=["reading"])
        def task(agent):
            return "executed"

        assert task(agent) == "executed"

    def test_missing_required_capabilities(self):
        agent = CodeAgent(system_prompt="Agent with no tools at all")
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(required_capabilities=["admin_access"])
        def task(agent):
            return "executed"

        with pytest.raises(KYAVerificationError, match="Missing capabilities"):
            task(agent)

    def test_tool_calling_agent_works(self):
        """Verify ToolCallingAgent works the same as CodeAgent."""
        agent = ToolCallingAgent(
            tools=[Tool("api_call", "Make API calls")],
            system_prompt="A tool-calling agent for API operations",
        )
        card = create_agent_card(agent, owner_name="T", owner_contact="t@t.com")
        attach_card(agent, card)

        @kya_verified(min_score=0)
        def task(agent):
            return "tool_calling_executed"

        assert task(agent) == "tool_calling_executed"
