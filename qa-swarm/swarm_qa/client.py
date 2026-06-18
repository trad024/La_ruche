"""
Swarm client wired to Ollama.

OpenAI Swarm talks to any OpenAI-compatible Chat Completions endpoint. Ollama exposes
exactly that at `${OLLAMA_BASE_URL}/v1`, so we point Swarm's underlying OpenAI client
there with a dummy api key (the deck uses `api_key="ollama"`).
"""

from __future__ import annotations

from functools import lru_cache

from openai import OpenAI
from swarm import Swarm

from swarm_qa.config import settings


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    return OpenAI(base_url=settings.openai_base_url, api_key=settings.ollama_api_key)


@lru_cache(maxsize=1)
def get_swarm() -> Swarm:
    """Return a process-wide Swarm client bound to the local Ollama server."""
    return Swarm(client=get_openai_client())
