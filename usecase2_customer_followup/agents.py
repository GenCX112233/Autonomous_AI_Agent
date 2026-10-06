"""
Use Case 2 - Autonomous Customer Follow-Up: Own the Issue Until Resolution.

Two tool-calling agents (see core/agent.ToolAgent) that genuinely act on a
real (sample) CRM application over HTTP, rather than just reasoning about
static text:

  CaseIntakeAgent      - looks at an interaction that couldn't be resolved
                          live and decides whether to open a persistent
                          follow-up case in the CRM.

  FollowUpOwnerAgent   - the persistent, per-case autonomous agent. On each
                          "tick" (representing time passing) it checks the
                          case/ticket state in the CRM, and decides whether
                          to create a backend ticket, escalate a stalled one,
                          proactively message the customer, or close the case.
"""
from typing import Any, Dict

from core.agent import ToolAgent
from core.tool import Tool
from crm.client import CRMClient
from llm.base import LLMClient


def build_case_intake_agent(llm: LLMClient, crm: CRMClient) -> ToolAgent:
    create_case_tool = Tool(
        name="create_case",
        description="Open a persistent follow-up case in the CRM for a customer issue that could not be resolved live.",
        parameters={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "summary": {"type": "string"},
                "category": {"type": "string"},
                "priority": {"type": "string", "enum": ["normal", "high"]},
            },
            "required": ["customer_id", "summary", "category"],
        },
        handler=crm.create_case,
    )
    return ToolAgent(
        name="CaseIntakeAgent",
        llm=llm,
        system_prompt=(
            "[AGENT:CASE_INTAKE] You are a case-intake agent for a contact center. You are given "
            "a completed interaction that could not be fully resolved live because it depends on "
            "a backend/back-office team. Use the create_case tool to open a persistent follow-up "
            "case owned by an autonomous agent, then give a one-sentence confirmation."
        ),
        tools=[create_case_tool],
    )


def build_followup_owner_agent(llm: LLMClient, crm: CRMClient) -> ToolAgent:
    tools = [
        Tool(
            name="get_case",
            description="Fetch the current state of a follow-up case (status, ticket_id, notes, etc).",
            parameters={"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
            handler=crm.get_case,
        ),
        Tool(
            name="create_ticket",
            description="Create a backend/back-office ticket for a case that doesn't have one yet.",
            parameters={
                "type": "object",
                "properties": {"case_id": {"type": "string"}, "summary": {"type": "string"}},
                "required": ["case_id", "summary"],
            },
            handler=crm.create_ticket,
        ),
        Tool(
            name="get_ticket_status",
            description="Check the current status of a backend ticket (pending/in_progress/resolved) and whether it is stalled.",
            parameters={"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]},
            handler=crm.get_ticket_status,
        ),
        Tool(
            name="escalate_ticket",
            description="Escalate a stalled backend ticket to expedite resolution.",
            parameters={
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["ticket_id", "reason"],
            },
            handler=crm.escalate_ticket,
        ),
        Tool(
            name="send_customer_update",
            description="Proactively message the customer with a progress or final-resolution update.",
            parameters={
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "message": {"type": "string"},
                    "update_type": {"type": "string", "enum": ["progress", "final"]},
                },
                "required": ["case_id", "message"],
            },
            handler=crm.send_customer_update,
        ),
        Tool(
            name="add_case_note",
            description="Add an internal note to the case's timeline.",
            parameters={
                "type": "object",
                "properties": {"case_id": {"type": "string"}, "note": {"type": "string"}},
                "required": ["case_id", "note"],
            },
            handler=crm.add_case_note,
        ),
        Tool(
            name="close_case",
            description="Close a case once it has been fully resolved and the customer has been informed.",
            parameters={"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
            handler=crm.close_case,
        ),
    ]
    return ToolAgent(
        name="FollowUpOwnerAgent",
        llm=llm,
        system_prompt=(
            "[AGENT:FOLLOWUP_OWNER] You are a persistent autonomous agent that owns a single "
            "customer follow-up case from initial interaction through final resolution. On each "
            "check-in: fetch the case, make sure a backend ticket exists, check its status, "
            "escalate it if it's stalled, proactively update the customer on progress (or the "
            "final resolution), and close the case once fully resolved. Use the tools to actually "
            "do this - don't just describe what you would do. Stop once you've taken the "
            "appropriate action(s) for this check-in."
        ),
        tools=tools,
    )


def run_intake(agent: ToolAgent, interaction: Dict[str, Any]) -> str:
    import json

    trace = agent.run(task=json.dumps(interaction))
    return trace.final_text


def run_followup_tick(agent: ToolAgent, case_id: str) -> "AgentTrace":  # noqa: F821
    import json

    return agent.run(task=json.dumps({"case_id": case_id}))
