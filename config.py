"""
Central configuration for CX Autopilot.

LLM provider is fully configurable via environment variable / .env file:
    LLM_PROVIDER=anthropic   -> uses Claude (requires ANTHROPIC_API_KEY)
    LLM_PROVIDER=openai      -> uses GPT      (requires OPENAI_API_KEY)
    LLM_PROVIDER=mock        -> uses a deterministic offline mock model
                                 (no API key / internet needed, great for
                                 demos, CI, and hackathon judging without
                                 handing out API keys)

Copy .env.example to .env and fill in the values you need.
"""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is optional; env vars can also be set directly.
    pass


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # ---- LLM configuration -------------------------------------------------
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock").strip().lower()  # anthropic | openai | mock

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-6-luna")

    max_agent_tool_turns: int = int(os.getenv("MAX_AGENT_TOOL_TURNS", "6"))

    # ---- CRM (Use Case 2 sample application) -------------------------------
    crm_base_url: str = os.getenv("CRM_BASE_URL", "http://127.0.0.1:8001")
    crm_data_file: str = os.getenv("CRM_DATA_FILE", os.path.join(os.path.dirname(__file__), "data", "crm_store.json"))
    auto_start_crm: bool = _env_bool("AUTO_START_CRM", True)

    # ---- Mock Genesys Cloud data --------------------------------------------
    genesys_mock_seed: int = int(os.getenv("GENESYS_MOCK_SEED", "42"))

    # ---- Human-in-the-loop behaviour (Use Case 1 supervisor gate) ----------
    auto_approve: bool = _env_bool("AUTO_APPROVE", False)


settings = Settings()
