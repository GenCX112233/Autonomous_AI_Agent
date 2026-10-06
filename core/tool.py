"""
A Tool wraps a plain Python callable with the JSON-schema metadata needed to
expose it to an LLM as a "function" it can call. The same Tool object can be
translated into either Anthropic's or OpenAI's function-calling schema, which
is what lets an agent's toolset stay identical regardless of LLM_PROVIDER.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema, e.g. {"type": "object", "properties": {...}, "required": [...]}
    handler: Callable[..., Any]

    def run(self, **kwargs) -> Any:
        return self.handler(**kwargs)

    def to_anthropic_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
