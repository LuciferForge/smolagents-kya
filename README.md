# smolagents-kya

KYA (Know Your Agent) identity verification for HuggingFace smolagents.

## Install

```bash
pip install smolagents-kya
```

## Quick Start

```python
from smolagents_kya import KYAToolCallingAgent

agent = KYAToolCallingAgent(
    name="my-agent",
    version="1.0.0",
    capabilities=["research", "summarization"]
)

card = agent.identity_card()
print(card)
```

## What is KYA?

Know Your Agent (KYA) is an identity standard for AI agents. It provides unique agent identity with Ed25519 signing, framework-native integration, and verifiable credentials.

See [kya-agent](https://github.com/LuciferForge/KYA) for the core library.

## Related

- [kya-agent](https://github.com/LuciferForge/KYA) — Core library
- [crewai-kya](https://github.com/LuciferForge/crewai-kya) — CrewAI
- [autogen-kya](https://github.com/LuciferForge/autogen-kya) — AutoGen
- [langchain-kya](https://github.com/LuciferForge/langchain-kya) — LangChain
- [llamaindex-kya](https://github.com/LuciferForge/llamaindex-kya) — LlamaIndex
- [dspy-kya](https://github.com/LuciferForge/dspy-kya) — DSPy

## License

MIT
