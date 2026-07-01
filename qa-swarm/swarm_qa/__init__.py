"""
swarm_qa — Autonomous testing system for the conversational agent.

A fleet of OpenAI-Swarm agents (Generator -> Executor -> Evaluator -> Reporter,
handoff model) that tests the conversational "agent under test" across three
channels (API / Web / Mobile), scores hallucinations, and detects regressions
between two versions of the target agent.

Powered entirely by local SLMs served by Ollama via its OpenAI-compatible API.
"""

__version__ = "0.1.0"
