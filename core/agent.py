"""
Generic agent building blocks used across all three use cases.

Agent          - a thin wrapper around an LLMClient with a fixed role/system
                 prompt. Good for single-shot "reason about this JSON and
                 give me back JSON" specialists (most of Use Case 1's swarm).

ToolAgent      - adds a real tool-calling loop: the LLM can call back into
                 Python functions (e.g. CRM operations) across multiple
                 turns until it's done. Used wherever an agent must actually
                 *act* on another system (Use Case 2's case-owner agent,
                 Use Case 3's supervisor).

Both are provider-agnostic: swap LLM_PROVIDER and nothing here changes.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.tool import Tool
from core.utils import extract_json
from llm.base import LLMClient, ToolCall
from config import settings


@dataclass
class AgentTrace:
    """Debug-friendly record of everything an agent did, useful for demos."""
    agent_name: str
    system_prompt: str
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    final_text: str = ""


class Agent:
    """A single-purpose specialist agent: one system prompt, one LLM call,
    JSON in -> JSON out. This is the workhorse for the Use Case 1 swarm
    (signal mining, root cause, fix, simulation, compliance, measurement)."""

    def __init__(self, name: str, llm: LLMClient, system_prompt: str):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt

    def run_json(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send `payload` as JSON, get back parsed JSON."""
        messages = [{"role": "user", "content": json.dumps(payload)}]
        response = self.llm.generate(system=self.system_prompt, messages=messages)
        try:
            return extract_json(response.text)
        except ValueError:
            # One retry with an explicit nudge - real LLMs occasionally wrap
            # JSON in prose despite instructions; the mock client never needs this.
            messages.append({"role": "assistant", "content": response.text})
            messages.append(
                {"role": "user", "content": "Respond with ONLY valid JSON, no commentary."}
            )
            response = self.llm.generate(system=self.system_prompt, messages=messages)
            return extract_json(response.text)


class ToolAgent:
    """An agent that can call real tools (Python functions) in a loop until
    it produces a final answer with no further tool calls, or a turn limit
    is hit. This is the closest analogue to native Claude/GPT tool use and
    is what actually drives the CRM in Use Case 2 and the analytics lookups
    in Use Case 3."""

    def __init__(self, name: str, llm: LLMClient, system_prompt: str, tools: List[Tool]):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.tools = tools
        self._tools_by_name = {t.name: t for t in tools}

    def run(self, task: str, max_turns: Optional[int] = None) -> AgentTrace:
        max_turns = max_turns or settings.max_agent_tool_turns
        messages: List[Dict[str, Any]] = [{"role": "user", "content": task}]
        trace = AgentTrace(agent_name=self.name, system_prompt=self.system_prompt)

        for _ in range(max_turns):
            response = self.llm.generate(system=self.system_prompt, messages=messages, tools=self.tools)

            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.text,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "input": tc.input} for tc in response.tool_calls
                ],
            }
            messages.append(assistant_msg)
            trace.transcript.append(assistant_msg)

            if not response.has_tool_calls:
                trace.final_text = response.text
                return trace

            for tc in response.tool_calls:
                result = self._execute_tool(tc)
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": json.dumps(result, default=str),
                }
                messages.append(tool_msg)
                trace.transcript.append(tool_msg)

        trace.final_text = "(stopped: reached max tool-call turns)"
        return trace

    def _execute_tool(self, tc: ToolCall) -> Any:
        tool = self._tools_by_name.get(tc.name)
        if tool is None:
            return {"error": f"Unknown tool '{tc.name}'"}
        try:
            return tool.run(**tc.input)
        except Exception as exc:  # keep the agent loop alive even if a tool fails
            return {"error": str(exc)}
