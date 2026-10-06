"""
Use Case 3 - Autonomous Supervisor: Ask Your Contact Center.

A supervisor asks a free-text question; a planning agent decides which
analytics sources are relevant, a tool-using agent fetches them, and a
reporting agent synthesizes findings into a concise report - including,
when relevant, per-agent coaching opportunities (interactions where an
agent showed a knowledge gap) and escalation-risk alerts (interactions
where the customer threatened to escalate to a regulator, ombudsman,
consumer forum, or similar).
"""
import json
from collections import defaultdict
from typing import Any, Dict

from core.agent import Agent, ToolAgent
from core.tool import Tool
from llm.base import LLMClient
from mock_genesys.data import generate_interactions, generate_todays_full_interaction_log, generate_wfm_snapshot
from usecase1_cx_optimization.agents import compute_stats


def _get_top_issues(**_) -> Dict[str, Any]:
    interactions = generate_interactions()
    groups: Dict[Any, list] = defaultdict(list)
    for i in interactions:
        if i["issue_tag"] != "none":
            groups[(i["flow_name"], i["issue_tag"])].append(i)
    top = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)[:5]
    return {
        "top_issues": [
            {"flow_name": f, "issue_tag": t, **compute_stats(items)} for (f, t), items in top
        ]
    }


def _get_sentiment_summary(**_) -> Dict[str, Any]:
    interactions = generate_interactions()
    return {"overall": compute_stats(interactions)}


def _get_wfm_summary(**_) -> Dict[str, Any]:
    return generate_wfm_snapshot()


def _get_agent_coaching_opportunities(**_) -> Dict[str, Any]:
    """Groups today's live-agent-handled interactions by agent and surfaces
    where a specific agent repeatedly showed the same knowledge gap - the
    raw facts a coaching recommendation would be based on."""
    interactions = [i for i in generate_todays_full_interaction_log() if i.get("knowledge_gap")]
    by_agent: Dict[str, list] = defaultdict(list)
    for i in interactions:
        by_agent[i["agent_id"]].append(i)

    opportunities = []
    for agent_id, items in by_agent.items():
        categories = sorted({i["knowledge_gap_category"] for i in items})
        opportunities.append(
            {
                "agent_id": agent_id,
                "agent_name": items[0]["agent_name"],
                "team": items[0]["team"],
                "interaction_count": len(items),
                "knowledge_gap_categories": categories,
                "avg_sentiment": compute_stats(items)["avg_sentiment"],
                "resolution_rate": compute_stats(items)["resolution_rate"],
                "sample_quote": items[0]["transcript"][1] if len(items[0]["transcript"]) > 1 else items[0]["transcript"][0],
                "coaching_context": items[0]["coaching_context"],
            }
        )
    opportunities.sort(key=lambda o: o["interaction_count"], reverse=True)
    return {"coaching_opportunities": opportunities}


def _get_escalation_risk_interactions(**_) -> Dict[str, Any]:
    """Surfaces every interaction today where the customer explicitly
    threatened to escalate outside the contact center (regulator, ombudsman,
    consumer forum, legal action) - these matter regardless of volume."""
    interactions = [i for i in generate_todays_full_interaction_log() if i.get("escalation_threat")]
    risks = [
        {
            "interaction_id": i["interaction_id"],
            "agent_id": i["agent_id"],
            "agent_name": i["agent_name"],
            "category": i["category"],
            "customer_quote": i["escalation_quote"],
            "sentiment_score": i["sentiment_score"],
            "resolved": i["resolved"],
        }
        for i in interactions
    ]
    return {"escalation_risks": risks}


def build_supervisor_planner(llm: LLMClient) -> Agent:
    return Agent(
        name="SupervisorPlanner",
        llm=llm,
        system_prompt=(
            "[AGENT:SUPERVISOR_PLAN] You are a planning agent for a contact-center supervisor "
            "assistant. Given a supervisor's free-text question, decide which analytics tools are "
            "needed: \"get_top_issues\" (recurring friction patterns), \"get_sentiment_summary\" "
            "(overall sentiment/handling), \"get_wfm_summary\" (staffing/service level), "
            "\"get_agent_coaching_opportunities\" (agents showing a repeated knowledge gap that "
            "needs coaching), \"get_escalation_risk_interactions\" (interactions where a customer "
            "threatened to escalate to a regulator, ombudsman, consumer forum, or similar - always "
            "include this one whenever the question could plausibly touch on customer complaints, "
            "escalation, regulators, or a full review of today's interactions, since these are rare "
            "but high-stakes and should not be missed). Respond with ONLY JSON: "
            "{\"analysis_plan\": [tool names in the order to call them, ...]}."
        ),
    )


def build_supervisor_analyst(llm: LLMClient) -> ToolAgent:
    tools = [
        Tool(
            name="get_top_issues",
            description="Get today's top recurring customer issues with volume/impact stats.",
            parameters={"type": "object", "properties": {}},
            handler=_get_top_issues,
        ),
        Tool(
            name="get_sentiment_summary",
            description="Get overall customer sentiment / handle time / resolution stats.",
            parameters={"type": "object", "properties": {}},
            handler=_get_sentiment_summary,
        ),
        Tool(
            name="get_wfm_summary",
            description="Get today's workforce-management snapshot (staffing, service level, occupancy).",
            parameters={"type": "object", "properties": {}},
            handler=_get_wfm_summary,
        ),
        Tool(
            name="get_agent_coaching_opportunities",
            description="Get agents whose interactions today show a repeated knowledge gap worth coaching.",
            parameters={"type": "object", "properties": {}},
            handler=_get_agent_coaching_opportunities,
        ),
        Tool(
            name="get_escalation_risk_interactions",
            description="Get interactions today where the customer threatened to escalate to a regulator, "
            "ombudsman, consumer forum, or similar outside body.",
            parameters={"type": "object", "properties": {}},
            handler=_get_escalation_risk_interactions,
        ),
    ]
    return ToolAgent(
        name="SupervisorAnalyst",
        llm=llm,
        system_prompt=(
            "[AGENT:SUPERVISOR_ANALYST] You are an analytics agent for a contact-center "
            "supervisor assistant. Call the analytics tools needed to answer the supervisor's "
            "question, then summarize your findings in one final message (no more tool calls)."
        ),
        tools=tools,
    )


def build_supervisor_reporter(llm: LLMClient) -> Agent:
    return Agent(
        name="SupervisorReporter",
        llm=llm,
        system_prompt=(
            "[AGENT:SUPERVISOR_REPORT] You are a reporting agent for a contact-center supervisor "
            "assistant. Given raw findings, write a concise report. If "
            "get_agent_coaching_opportunities findings are present, turn each one into a specific, "
            "actionable coaching recommendation for that named agent. If "
            "get_escalation_risk_interactions findings are present, treat every one as urgent: give "
            "each a severity and a concrete recommended action, regardless of how few there are. "
            "Respond with ONLY JSON: {\"report\": str, \"recommended_investigation\": [str, ...], "
            "\"coaching_recommendations\": [{\"agent_name\": str, \"team\": str, \"knowledge_gap\": "
            "str, \"recommendation\": str}, ...], \"escalation_alerts\": [{\"interaction_id\": str, "
            "\"agent_name\": str, \"customer_quote\": str, \"severity\": \"high\"|\"medium\", "
            "\"recommended_action\": str}, ...]}. Omit coaching_recommendations/escalation_alerts "
            "entries (empty arrays) when there were no corresponding findings - never invent them."
        ),
    )


def answer_supervisor_question(llm: LLMClient, question: str) -> Dict[str, Any]:
    planner = build_supervisor_planner(llm)
    plan = planner.run_json({"question": question})

    analyst = build_supervisor_analyst(llm)
    trace = analyst.run(
        task=json.dumps({"question": question, "analysis_plan": plan.get("analysis_plan", [])})
    )
    findings = {}
    for msg in trace.transcript:
        if msg["role"] == "tool":
            try:
                findings[msg["name"]] = json.loads(msg["content"])
            except Exception:
                findings[msg["name"]] = msg["content"]

    reporter = build_supervisor_reporter(llm)
    report = reporter.run_json({"question": question, "findings": findings})
    return {"plan": plan, "findings": findings, "report": report}
