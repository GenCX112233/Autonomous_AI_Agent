"""
A deterministic, offline stand-in for a real LLM.

Why this exists:
  - Lets the ENTIRE multi-agent pipeline (Use Cases 1, 2 and 3) run and be
    demoed with zero API keys and zero internet access.
  - Useful for automated tests / CI so the agent orchestration logic can be
    verified independently of a real model's non-determinism.

How it works:
  Every agent in this project tags its system prompt with a marker like
  "[AGENT:ROOT_CAUSE]". The mock client looks for that marker and routes to a
  small, rule-based generator that inspects the JSON payload embedded in the
  user message and fabricates a *plausible, schema-correct* response - the
  same shape a real Claude/GPT call would be asked to produce. This keeps the
  mock genuinely exercising the data flow between agents rather than just
  returning canned strings.

  For agents that use native tool-calling (ToolAgent), the mock also knows
  how to emit a ToolCall so the tool-execution loop in core/agent.py gets
  exercised end-to-end too.
"""
import json
import re
import uuid
from typing import Any, Dict, List, Optional

from llm.base import LLMClient, LLMResponse, ToolCall


def _extract_tag(system: str) -> str:
    m = re.search(r"\[AGENT:([A-Z0-9_]+)\]", system)
    return m.group(1) if m else "UNKNOWN"


def _last_user_json(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Best-effort: find the most recent user message and parse embedded JSON."""
    for m in reversed(messages):
        if m["role"] == "user":
            try:
                return json.loads(m["content"])
            except Exception:
                # Try to find a {...} block inside free text
                match = re.search(r"\{.*\}", m["content"], re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except Exception:
                        return {}
            return {}
    return {}


def _has_tool_result_for(messages: List[Dict[str, Any]], name: str) -> bool:
    return any(m["role"] == "tool" and m.get("name") == name for m in messages)


class MockClient(LLMClient):
    """Deterministic offline model. See module docstring."""

    def generate(self, system: str, messages: List[Dict[str, Any]], tools: Optional[List] = None) -> LLMResponse:
        tag = _extract_tag(system)
        payload = _last_user_json(messages)
        handler = getattr(self, f"_h_{tag.lower()}", None)

        if handler is not None:
            return handler(payload, messages, tools)

        # Generic tool-using agents (no dedicated handler): drive them with a
        # simple greedy policy so the ToolAgent loop still terminates sensibly.
        if tools:
            return self._generic_tool_policy(payload, messages, tools)

        return LLMResponse(text=json.dumps({"note": f"mock: no handler for tag {tag}"}))

    # ------------------------------------------------------------------ #
    # Use Case 1: Autonomous CX Optimization
    # ------------------------------------------------------------------ #
    def _h_signal_mining(self, payload, messages, tools):
        stats = payload.get("stats", {})
        issue_tag = payload.get("issue_tag", "unknown_issue")
        flow_name = payload.get("flow_name", "unknown_flow")
        count = stats.get("count", 0)
        avg_sentiment = stats.get("avg_sentiment", 0)
        resolution_rate = stats.get("resolution_rate", 1.0)
        priority = round(count * (1 - resolution_rate) * (1.2 - avg_sentiment), 2)
        out = {
            "summary": (
                f"{count} interactions on '{flow_name}' tagged '{issue_tag}' show a "
                f"{round((1 - resolution_rate) * 100)}% failure-to-resolve rate and "
                f"below-average sentiment ({avg_sentiment}). Customers appear to be "
                f"looping or abandoning rather than completing their task."
            ),
            "customer_impact": "high" if priority > 3 else "medium" if priority > 1 else "low",
            "priority_score": priority,
        }
        return LLMResponse(text=json.dumps(out))

    def _h_root_cause(self, payload, messages, tools):
        flow_steps = payload.get("flow_steps", [])
        issue_tag = payload.get("issue_tag", "issue")
        offending = flow_steps[1] if len(flow_steps) > 1 else (flow_steps[0] if flow_steps else {})
        out = {
            "offending_step_id": offending.get("step_id", "unknown"),
            "root_cause_explanation": (
                f"Step '{offending.get('step_id', 'unknown')}' "
                f"(\"{offending.get('text', '')[:80]}\") does not give customers a clear, "
                f"low-effort path forward for '{issue_tag}', causing repeated loops, "
                f"transfers, or abandonment before resolution."
            ),
            "confidence": 0.82,
        }
        return LLMResponse(text=json.dumps(out))

    def _h_fix_proposal(self, payload, messages, tools):
        flow_steps = payload.get("flow_steps", [])
        offending_step_id = payload.get("offending_step_id")
        new_steps = []
        changed = False
        for step in flow_steps:
            step_copy = dict(step)
            if step.get("step_id") == offending_step_id and not changed:
                step_copy["text"] = step["text"] + " [Clarified: added explicit self-service option and a direct 'talk to a person' fallback.]"
                changed = True
            new_steps.append(step_copy)
        out = {
            "change_description": "Clarify the ambiguous step with an explicit self-service action and a guaranteed live-agent fallback.",
            "rationale": "Removing ambiguity and guaranteeing an escape hatch reduces repeat loops and abandonment for confused or frustrated customers.",
            "proposed_flow_steps": new_steps,
        }
        return LLMResponse(text=json.dumps(out))

    def _h_simulation_persona(self, payload, messages, tools):
        persona = payload.get("persona", "average_customer")
        difficulty = {
            "confused_customer": 1.3,
            "frustrated_customer": 1.2,
            "elderly_customer": 1.4,
            "non_native_speaker": 1.35,
        }.get(persona, 1.0)

        old_resolution = round(max(0.15, 0.55 / difficulty), 2)
        new_resolution = round(min(0.97, old_resolution * 1.45), 2)
        old_effort = round(min(5, 2.5 * difficulty), 1)
        new_effort = round(max(1, old_effort - 1.4), 1)
        old_frustration = round(min(5, 2.3 * difficulty), 1)
        new_frustration = round(max(1, old_frustration - 1.3), 1)

        out = {
            "persona": persona,
            "old": {
                "resolution_likelihood": old_resolution,
                "effort_score_1_5": old_effort,
                "frustration_score_1_5": old_frustration,
                "estimated_handle_time_seconds": round(180 * difficulty),
            },
            "new": {
                "resolution_likelihood": new_resolution,
                "effort_score_1_5": new_effort,
                "frustration_score_1_5": new_frustration,
                "estimated_handle_time_seconds": round(120 * difficulty),
            },
            "narrative": (
                f"As a {persona.replace('_', ' ')}, the new flow reaches the goal in fewer "
                f"steps and offers a clearer fallback, reducing effort and frustration versus "
                f"the original flow."
            ),
        }
        return LLMResponse(text=json.dumps(out))

    def _h_compliance_check(self, payload, messages, tools):
        change_description = (payload.get("change_description") or "").lower()
        violations = []
        if "remove" in change_description and "agent" in change_description:
            violations.append("Change may remove ability to reach a live agent.")
        verdict = "FLAGGED" if violations else "APPROVED"
        out = {
            "verdict": verdict,
            "risk_level": "high" if violations else "low",
            "violations": violations,
            "notes": "No policy conflicts detected." if not violations else "Review flagged items before deployment.",
        }
        return LLMResponse(text=json.dumps(out))

    def _h_measurement(self, payload, messages, tools):
        before = payload.get("before_stats", {})
        after = payload.get("after_stats", {})
        before_res = before.get("resolution_rate", 0) or 0
        after_res = after.get("resolution_rate", 0) or 0
        before_sent = before.get("avg_sentiment", 0) or 0
        after_sent = after.get("avg_sentiment", 0) or 0
        improved = after_res >= before_res and after_sent >= before_sent
        verdict = "an improvement" if improved else "NOT a clear improvement (regressed on at least one metric)"
        out = {
            "impact_summary": (
                f"Post-deployment resolution rate moved from {before_res} to {after_res}, "
                f"and average sentiment moved from {before_sent} to {after_sent}. "
                f"The change is measured as {verdict}."
            ),
            "recommendation": "keep_change" if improved else "roll_back",
        }
        return LLMResponse(text=json.dumps(out))

    # ------------------------------------------------------------------ #
    # Use Case 2: Autonomous Customer Follow-Up (tool-calling agents)
    # ------------------------------------------------------------------ #
    def _h_case_intake(self, payload, messages, tools):
        # First turn: decide + call create_case. Second turn: wrap up.
        if not _has_tool_result_for(messages, "create_case"):
            interaction = payload
            tool = self._find_tool(tools, "create_case")
            if tool and interaction:
                return LLMResponse(
                    text="",
                    tool_calls=[
                        ToolCall(
                            id=str(uuid.uuid4()),
                            name="create_case",
                            input={
                                "customer_id": interaction.get("customer_id", ""),
                                "summary": interaction.get("summary", "Follow-up required"),
                                "category": interaction.get("issue_tag", "general"),
                                "priority": "high" if interaction.get("sentiment_score", 0) < -0.2 else "normal",
                            },
                        )
                    ],
                )
        return LLMResponse(text="Case created for post-contact follow-up.")

    def _h_followup_owner(self, payload, messages, tools):
        """
        Greedy but sensible policy for the persistent follow-up agent:
          1. get_case
          2. if no ticket yet -> create_ticket
          3. get_ticket_status
          4. if resolved -> send_customer_update(final) then close_case
             elif stalled -> escalate_ticket, then send_customer_update(progress)
             else -> send_customer_update(progress) only every other tick (handled by caller cadence)
        """
        tool_names_called = [m.get("name") for m in messages if m["role"] == "tool"]

        def call(name, **kwargs):
            return LLMResponse(text="", tool_calls=[ToolCall(id=str(uuid.uuid4()), name=name, input=kwargs)])

        case_id = payload.get("case_id")

        if "get_case" not in tool_names_called:
            return call("get_case", case_id=case_id)

        # find the get_case result
        case_result = self._latest_tool_result(messages, "get_case")
        ticket_id = case_result.get("ticket_id") if case_result else None

        if not ticket_id and "create_ticket" not in tool_names_called:
            return call(
                "create_ticket",
                case_id=case_id,
                summary=case_result.get("summary", "") if case_result else "",
            )

        if "get_ticket_status" not in tool_names_called:
            ticket_id = ticket_id or self._latest_tool_result(messages, "create_ticket", {}).get("ticket_id")
            return call("get_ticket_status", ticket_id=ticket_id)

        status_result = self._latest_tool_result(messages, "get_ticket_status") or {}
        status = status_result.get("status", "pending")
        stalled = status_result.get("is_stalled", False)

        if status == "resolved":
            if "send_customer_update" not in tool_names_called:
                return call(
                    "send_customer_update",
                    case_id=case_id,
                    message=(
                        "Good news - your issue has been fully resolved by our back-office "
                        "team. No further action is needed on your end. Thank you for your "
                        "patience!"
                    ),
                    update_type="final",
                )
            if "close_case" not in tool_names_called:
                return call("close_case", case_id=case_id)
            return LLMResponse(text="Case resolved and closed; customer notified.")

        if stalled and "escalate_ticket" not in tool_names_called:
            ticket_id = status_result.get("ticket_id") or ticket_id
            return call("escalate_ticket", ticket_id=ticket_id, reason="No backend movement past SLA threshold.")

        if "send_customer_update" not in tool_names_called:
            note = "escalated to expedite a resolution" if stalled else f"currently '{status}' with our back-office team"
            return call(
                "send_customer_update",
                case_id=case_id,
                message=f"Quick update on your case: it is {note}. We'll keep you posted.",
                update_type="progress",
            )

        return LLMResponse(text="No further action needed this cycle; case remains open and customer is informed.")

    # ------------------------------------------------------------------ #
    # Use Case 3: Autonomous Supervisor
    # ------------------------------------------------------------------ #
    def _h_supervisor_plan(self, payload, messages, tools):
        question = (payload.get("question") or "").lower()
        plan = []
        full_review_terms = ("all interaction", "full review", "review today", "review all", "everything that happened")
        if any(term in question for term in full_review_terms):
            # A comprehensive sweep: issues, sentiment, staffing, coaching, and escalation risk together.
            plan = [
                "get_top_issues",
                "get_sentiment_summary",
                "get_wfm_summary",
                "get_agent_coaching_opportunities",
                "get_escalation_risk_interactions",
            ]
        else:
            if "issue" in question or "problem" in question:
                plan.append("get_top_issues")
            if "handle time" in question or "aht" in question:
                plan.append("get_wfm_summary")
            if "frustrat" in question or "sentiment" in question:
                plan.append("get_sentiment_summary")
            if "transfer" in question:
                plan.append("get_top_issues")
            if any(term in question for term in ("coach", "knowledge gap", "training", "skill gap")):
                plan.append("get_agent_coaching_opportunities")
            if any(
                term in question
                for term in (
                    "escalat", "consumer complaint", "consumer forum", "regulator", "ombudsman",
                    "government", "legal action", "consumer court",
                )
            ):
                plan.append("get_escalation_risk_interactions")
        if not plan:
            plan = ["get_top_issues", "get_sentiment_summary", "get_wfm_summary"]
        return LLMResponse(text=json.dumps({"analysis_plan": list(dict.fromkeys(plan))}))

    def _h_supervisor_analyst(self, payload, messages, tools):
        plan = payload.get("analysis_plan") or [t.name for t in (tools or [])]
        called = {m.get("name") for m in messages if m["role"] == "tool"}
        for tool_name in plan:
            if tool_name not in called:
                return LLMResponse(
                    text="", tool_calls=[ToolCall(id=str(uuid.uuid4()), name=tool_name, input={})]
                )
        return LLMResponse(text="Findings gathered for the supervisor's question.")

    def _h_supervisor_report(self, payload, messages, tools):
        findings = payload.get("findings", {})
        lines = []
        for k, v in findings.items():
            if k in ("get_agent_coaching_opportunities", "get_escalation_risk_interactions"):
                continue  # rendered into their own structured sections below, not the prose summary
            lines.append(f"- {k}: {v}")

        coaching_recommendations = []
        for opp in findings.get("get_agent_coaching_opportunities", {}).get("coaching_opportunities", []):
            gap = opp["knowledge_gap_categories"][0].replace("_", " ") if opp["knowledge_gap_categories"] else "a process gap"
            coaching_recommendations.append(
                {
                    "agent_name": opp["agent_name"],
                    "team": opp["team"],
                    "knowledge_gap": gap,
                    "recommendation": (
                        f"{opp['agent_name']} showed this gap in {opp['interaction_count']} interactions today "
                        f"(avg. sentiment {opp['avg_sentiment']}). {opp['coaching_context']} Schedule a short "
                        f"coaching session on {gap} and confirm understanding with a follow-up call review."
                    ),
                }
            )

        escalation_alerts = []
        for risk in findings.get("get_escalation_risk_interactions", {}).get("escalation_risks", []):
            severity = "high" if risk["sentiment_score"] <= -0.75 or not risk["resolved"] else "medium"
            escalation_alerts.append(
                {
                    "interaction_id": risk["interaction_id"],
                    "agent_name": risk["agent_name"],
                    "customer_quote": risk["customer_quote"],
                    "severity": severity,
                    "recommended_action": (
                        "Escalate to a senior specialist and proactively contact the customer with a "
                        "resolution within one business day, before any formal complaint is filed."
                        if severity == "high"
                        else "Follow up with the customer to confirm the issue is fully resolved and log it "
                        "for the compliance team's awareness."
                    ),
                }
            )

        report_text = "Supervisor report:\n" + "\n".join(lines) if lines else "Supervisor report: no issue/sentiment/staffing findings were requested for this question."
        if not lines and not coaching_recommendations and not escalation_alerts:
            report_text = "No anomalies found."
        if coaching_recommendations:
            report_text += (
                f"\n\n{len(coaching_recommendations)} agent(s) show a repeated knowledge gap worth coaching - "
                "see the coaching recommendations below."
            )
        if escalation_alerts:
            report_text += (
                f"\n\n{len(escalation_alerts)} interaction(s) today included an explicit threat to escalate "
                "outside the contact center (regulator, ombudsman, consumer forum, or legal action) - see the "
                "escalation alerts below. These need attention regardless of how few there are."
            )

        out = {
            "report": report_text,
            "recommended_investigation": [
                "Review the top friction cluster's IVR/bot flow for a possible fix.",
                "Check staffing alignment during the peak interaction window.",
            ],
            "coaching_recommendations": coaching_recommendations,
            "escalation_alerts": escalation_alerts,
        }
        return LLMResponse(text=json.dumps(out))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _find_tool(tools, name):
        if not tools:
            return None
        for t in tools:
            if t.name == name:
                return t
        return None

    @staticmethod
    def _latest_tool_result(messages, name, default=None):
        for m in reversed(messages):
            if m["role"] == "tool" and m.get("name") == name:
                content = m.get("content")
                if isinstance(content, str):
                    try:
                        return json.loads(content)
                    except Exception:
                        return default if default is not None else {}
                return content
        return default if default is not None else {}

    def _generic_tool_policy(self, payload, messages, tools):
        """Fallback for any tool-agent without a dedicated mock handler:
        call the first tool once, then stop."""
        called = {m.get("name") for m in messages if m["role"] == "tool"}
        for t in tools:
            if t.name not in called:
                return LLMResponse(
                    text="", tool_calls=[ToolCall(id=str(uuid.uuid4()), name=t.name, input={})]
                )
        return LLMResponse(text="Done.")
