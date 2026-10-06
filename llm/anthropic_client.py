"""
Claude backend. Talks to the real Anthropic API using the official SDK.
Only imported/instantiated when LLM_PROVIDER=anthropic, so the rest of the
system works fine even if the `anthropic` package isn't installed.
"""
import json
from typing import Any, Dict, List, Optional

from llm.base import LLMClient, LLMResponse, ToolCall


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str, max_tokens: int = 2000):
        import anthropic  # local import: optional dependency

        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file or "
                "switch LLM_PROVIDER to 'mock' / 'openai'."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, system: str, messages: List[Dict[str, Any]], tools: Optional[List] = None) -> LLMResponse:
        anthropic_messages = []
        for m in messages:
            role = m["role"]
            if role == "user":
                anthropic_messages.append({"role": "user", "content": m["content"]})
            elif role == "assistant":
                content = []
                if m.get("content"):
                    content.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls", []):
                    content.append(
                        {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["input"]}
                    )
                anthropic_messages.append({"role": "assistant", "content": content})
            elif role == "tool":
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m["tool_call_id"],
                                "content": str(m["content"]),
                            }
                        ],
                    }
                )

        kwargs: Dict[str, Any] = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=anthropic_messages,
        )
        if tools:
            kwargs["tools"] = [t.to_anthropic_schema() for t in tools]

        resp = self._client.messages.create(**kwargs)

        text = ""
        tool_calls: List[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        return LLMResponse(text=text, tool_calls=tool_calls, raw=resp)
