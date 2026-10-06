"""
Provider-agnostic types shared by every LLM backend (Claude / GPT / mock).

Every concrete client (AnthropicClient, OpenAIClient, MockClient) speaks this
common "dialect" so the rest of the codebase - agents, orchestrators - never
needs to know which model is actually answering. This is what makes the LLM
provider a single config switch (see config.py: LLM_PROVIDER).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


# Generic transcript message shapes (all plain dicts, kept provider-agnostic):
#   {"role": "user", "content": "<text>"}
#   {"role": "assistant", "content": "<text or ''>", "tool_calls": [ToolCall-ish dicts]}
#   {"role": "tool", "tool_call_id": "...", "name": "...", "content": "<string>"}


class LLMClient(ABC):
    """Abstract interface every LLM backend must implement."""

    @abstractmethod
    def generate(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List["Tool"]] = None,  # noqa: F821 (Tool defined in core.tool)
    ) -> LLMResponse:
        """Send the full conversation so far and get the next model turn."""
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.__class__.__name__
