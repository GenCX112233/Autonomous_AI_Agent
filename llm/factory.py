"""
Single switch for "which model powers every agent".

    from llm.factory import get_llm_client
    llm = get_llm_client()

Change LLM_PROVIDER in .env (or pass provider="anthropic"/"openai"/"mock"
explicitly) and every agent in Use Cases 1, 2 and 3 uses the new model - no
other code changes needed.
"""
from typing import Optional

from config import settings
from llm.base import LLMClient


def get_llm_client(provider: Optional[str] = None) -> LLMClient:
    provider = (provider or settings.llm_provider or "mock").strip().lower()

    if provider == "anthropic":
        from llm.anthropic_client import AnthropicClient

        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    if provider == "openai":
        from llm.openai_client import OpenAIClient

        return OpenAIClient(api_key=settings.openai_api_key, model=settings.openai_model)

    if provider == "mock":
        from llm.mock_client import MockClient

        return MockClient()

    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Use 'anthropic', 'openai', or 'mock'.")
