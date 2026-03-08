"""smolagents-kya — KYA (Know Your Agent) identity verification for HuggingFace smolagents.

Provides tools, decorators, and helpers to bring cryptographic agent identity
to smolagents workflows. No blockchain, no cloud dependency — just Ed25519 signatures.

Usage:
    from smolagents_kya import KYAIdentityTool, TrustGateTool, create_agent_card, attach_card
"""

__version__ = "0.1.0"

from smolagents_kya.card import create_agent_card, attach_card, get_card
from smolagents_kya.identity import KYAIdentityTool
from smolagents_kya.trust_gate import TrustGateTool
from smolagents_kya.middleware import kya_verified

__all__ = [
    "KYAIdentityTool",
    "TrustGateTool",
    "kya_verified",
    "create_agent_card",
    "attach_card",
    "get_card",
]
