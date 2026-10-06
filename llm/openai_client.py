"""
GPT backend. Talks to the real OpenAI API using the official SDK.
Only imported/instantiated when LLM_PROVIDER=openai.
"""
import json
from typing import Any, Dict, List, Optional

from llm.base import LLMClient, LLMResponse, ToolCall


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str):
        from openai import OpenAI  # local import: optional dependency

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to your .env file or "
                "switch LLM_PROVIDER to 'mock' / 'anthropic'."
            )
        self._client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, system: str, messages: List[Dict[str, Any]], tools: Optional[List] = None) -> LLMResponse:
        oai_messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        for m in messages:
            role = m["role"]
            if role == "user":
                oai_messages.append({"role": "user", "content": m["content"]})
            elif role == "assistant":
                msg: Dict[str, Any] = {"role": "assistant", "content": m.get("content") or None}
                if m.get("tool_calls"):
                    msg["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": json.dumps(tc["input"])},
                        }
                        for tc in m["tool_calls"]
                    ]
                oai_messages.append(msg)
            elif role == "tool":
                oai_messages.append(
                    {"role": "tool", "tool_call_id": m["tool_call_id"], "content": str(m["content"])}
                )

        kwargs: Dict[str, Any] = dict(model=self.model, messages=oai_messages)
        if tools:
            kwargs["tools"] = [t.to_openai_schema() for t in tools]
            # GPT-6 Luna's Chat Completions function calling requires none.
            # Requests without tools retain the model's default reasoning.
            if self.model == "gpt-6-luna":
                kwargs["reasoning_effort"] = "none"

        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message

        tool_calls: List[ToolCall] = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))

        return LLMResponse(text=choice.content or "", tool_calls=tool_calls, raw=resp)
