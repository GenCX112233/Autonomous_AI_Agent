"""
Stand-in for the Genesys Cloud APIs (Analytics/Conversations + Architect).

In a real deployment, CX Autopilot's signal-mining swarm would pull
conversation analytics and transcripts from Genesys Cloud, and the fix
agents would read/write Architect flow definitions via the Genesys Cloud
API. Here we generate a reproducible synthetic dataset so the whole
multi-agent pipeline can be demoed and tested without a live org.
"""
import random
from typing import Any, Dict, List

from config import settings

# ---------------------------------------------------------------------------
# Architect flow definitions (simplified) - the thing Root Cause / Fix agents
# reason about and edit.
# ---------------------------------------------------------------------------
FLOWS: Dict[str, List[Dict[str, str]]] = {
    "billing_ivr": [
        {"step_id": "greet", "type": "prompt", "text": "Welcome to billing support."},
        {"step_id": "menu", "type": "menu", "text": "Press 1 for balance, 2 for payment, 3 for disputes."},
        {"step_id": "dispute_path", "type": "prompt", "text": "Please describe your dispute after the tone."},
        {"step_id": "confirm", "type": "prompt", "text": "Your request has been logged."},
    ],
    "password_reset_bot": [
        {"step_id": "greet", "type": "bot_prompt", "text": "Hi! I can help you reset your password."},
        {"step_id": "verify", "type": "bot_prompt", "text": "Please enter the 6-digit code we texted you."},
        {"step_id": "reset", "type": "bot_prompt", "text": "Enter your new password now."},
        {"step_id": "done", "type": "bot_prompt", "text": "Your password has been reset."},
    ],
    "address_change_ivr": [
        {"step_id": "greet", "type": "prompt", "text": "Welcome to account services."},
        {"step_id": "menu", "type": "menu", "text": "For address changes, press 4."},
        {"step_id": "address_capture", "type": "prompt", "text": "Please say your new address after the tone."},
        {"step_id": "confirm", "type": "prompt", "text": "Thanks, your address change is being processed."},
    ],
    "order_status_ivr": [
        {"step_id": "greet", "type": "prompt", "text": "Welcome to order status."},
        {"step_id": "lookup", "type": "prompt", "text": "Please enter your 10-digit order number."},
        {"step_id": "status", "type": "prompt", "text": "Here is the current status of your order."},
    ],
}

# ---------------------------------------------------------------------------
# Friction scenarios used to generate realistic clusters of struggling
# interactions (what the signal-mining swarm should discover).
# ---------------------------------------------------------------------------
_FRICTION_SCENARIOS = [
    dict(
        flow_name="billing_ivr",
        issue_tag="dispute_loop",
        n=18,
        base_sentiment=-0.45,
        base_handle_time=340,
        resolved_rate=0.30,
        transfers=1.6,
        sample_turns=[
            "Customer: I want to dispute this charge.",
            "IVR: Please describe your dispute after the tone.",
            "Customer: (describes charge) ... nothing happens, gets transferred.",
        ],
    ),
    dict(
        flow_name="password_reset_bot",
        issue_tag="otp_not_received",
        n=22,
        base_sentiment=-0.55,
        base_handle_time=280,
        resolved_rate=0.25,
        transfers=1.2,
        sample_turns=[
            "Bot: Please enter the 6-digit code we texted you.",
            "Customer: I never got a code.",
            "Bot: Please enter the 6-digit code we texted you.",
            "Customer: (repeats, gives up, calls agent)",
        ],
    ),
    dict(
        flow_name="address_change_ivr",
        issue_tag="speech_recognition_failure",
        n=15,
        base_sentiment=-0.35,
        base_handle_time=260,
        resolved_rate=0.40,
        transfers=1.4,
        sample_turns=[
            "IVR: Please say your new address after the tone.",
            "Customer: 42 Baker Street, Apartment 3B.",
            "IVR: Sorry, I didn't get that. Please say your new address.",
        ],
    ),
    dict(
        flow_name="order_status_ivr",
        issue_tag="ambiguous_status_language",
        n=12,
        base_sentiment=-0.20,
        base_handle_time=150,
        resolved_rate=0.55,
        transfers=0.6,
        sample_turns=[
            "IVR: Your order is 'in process'.",
            "Customer: What does that mean, has it shipped or not?",
        ],
    ),
    # A healthy baseline flow/issue mix so clustering has contrast, not just friction.
    dict(
        flow_name="order_status_ivr",
        issue_tag="none",
        n=25,
        base_sentiment=0.35,
        base_handle_time=90,
        resolved_rate=0.95,
        transfers=0.05,
        sample_turns=["IVR: Your order shipped yesterday.", "Customer: Great, thanks!"],
    ),
]

_PERSONAS = ["average_customer", "confused_customer", "frustrated_customer", "elderly_customer", "non_native_speaker"]
_CHANNELS = ["voice", "chat"]

# ---------------------------------------------------------------------------
# Human agent roster + live-agent-handled interactions, used by Use Case 3's
# "review everything that happened today" tools (coaching opportunities,
# escalation risk). Kept separate from the IVR/bot FLOWS/_FRICTION_SCENARIOS
# above so Use Case 1's clustering - which expects exactly the 4 known
# flow/issue combinations - is unaffected by this dataset.
# ---------------------------------------------------------------------------
AGENTS = [
    {"agent_id": "AG-101", "name": "Maya Chen", "team": "Billing"},
    {"agent_id": "AG-102", "name": "Arjun Mehta", "team": "Billing"},
    {"agent_id": "AG-103", "name": "Priya Raman", "team": "Retention"},
    {"agent_id": "AG-104", "name": "Daniel Osei", "team": "Technical Support"},
    {"agent_id": "AG-105", "name": "Lucia Fernandez", "team": "Technical Support"},
    {"agent_id": "AG-106", "name": "Sam Okoye", "team": "Retention"},
]

# Each scenario deliberately repeats the same agent + category so the
# coaching tool has a real pattern to surface (one agent, one clear gap),
# rather than noise scattered evenly across the whole roster.
_KNOWLEDGE_GAP_SCENARIOS = [
    dict(
        agent_id="AG-102",
        category="refund_policy_exception",
        n=11,
        base_sentiment=-0.4,
        base_handle_time=310,
        resolved_rate=0.35,
        transfers=0.5,
        sample_turns=[
            "Customer: I was told last week that refunds for cancelled add-ons are automatic now.",
            "Agent: I'm not seeing that in my system - I don't think we do that.",
            "Customer: Your colleague processed one for me exactly like this last month.",
        ],
        coaching_context="Does not know about the updated add-on refund policy introduced last month; "
        "keeps telling customers the exception doesn't exist instead of applying it.",
    ),
    dict(
        agent_id="AG-104",
        category="loyalty_tier_benefits",
        n=8,
        base_sentiment=-0.3,
        base_handle_time=260,
        resolved_rate=0.45,
        transfers=0.3,
        sample_turns=[
            "Customer: As a Gold member I should get free installation on this order.",
            "Agent: I don't see that benefit listed, are you sure that's part of your plan?",
            "Customer: It's listed on your own loyalty page.",
        ],
        coaching_context="Unfamiliar with Gold-tier loyalty benefits (free installation); doesn't check "
        "the loyalty benefits reference before telling the customer it doesn't exist.",
    ),
    dict(
        agent_id="AG-106",
        category="plan_downgrade_process",
        n=7,
        base_sentiment=-0.25,
        base_handle_time=290,
        resolved_rate=0.4,
        transfers=0.6,
        sample_turns=[
            "Customer: I just want to downgrade to the lighter plan, like your website says I can do myself.",
            "Agent: That has to go through retention, let me transfer you.",
            "Customer: I was transferred for this exact thing yesterday too.",
        ],
        coaching_context="Routes every downgrade request to retention instead of using the new self-serve "
        "downgrade path for this plan type; unaware the direct path now exists.",
    ),
]

# A handful of distinct, high-severity interactions where the customer
# explicitly threatens to escalate outside the contact center - to a
# regulator, ombudsman, consumer forum, or similar. These need their own
# detection path since they're rare, cut across categories, and matter
# regardless of how the rest of the interaction went.
_ESCALATION_SCENARIOS = [
    dict(
        category="billing_dispute_escalation",
        quote="If this overcharge isn't fixed today, I'm filing a complaint with the consumer forum "
        "and writing directly to your regulator.",
        sentiment=-0.8,
        resolved=False,
        agent_id="AG-101",
    ),
    dict(
        category="service_outage_compensation",
        quote="This is the third outage this month with no compensation. I'll be escalating this to "
        "the ombudsman and posting about it publicly if nothing changes.",
        sentiment=-0.75,
        resolved=False,
        agent_id="AG-105",
    ),
    dict(
        category="data_privacy_concern",
        quote="You shared my account details with someone else without my consent. I'm reporting this "
        "to the data protection authority.",
        sentiment=-0.85,
        resolved=False,
        agent_id="AG-103",
    ),
    dict(
        category="repeated_overcharge",
        quote="I've called five times about this same overcharge. My next call is to consumer court, "
        "not your call center.",
        sentiment=-0.7,
        resolved=True,
        agent_id="AG-102",
    ),
    dict(
        category="contract_cancellation_dispute",
        quote="You are refusing to honor the cancellation terms I signed. I will be taking this to a "
        "government consumer helpline and my lawyer.",
        sentiment=-0.78,
        resolved=False,
        agent_id="AG-106",
    ),
]


def _agent_by_id(agent_id: str) -> Dict[str, str]:
    return next(a for a in AGENTS if a["agent_id"] == agent_id)


def generate_knowledge_gap_interactions(seed: int = None) -> List[Dict[str, Any]]:
    """Live-agent-handled interactions where the agent demonstrably lacked
    knowledge of a policy/process - the raw material for Use Case 3's
    agent-coaching tool."""
    rng = random.Random((seed if seed is not None else settings.genesys_mock_seed) + 4242)
    interactions = []
    counter = 1
    for scenario in _KNOWLEDGE_GAP_SCENARIOS:
        agent = _agent_by_id(scenario["agent_id"])
        for _ in range(scenario["n"]):
            interactions.append(
                {
                    "interaction_id": f"AGT-{counter:04d}",
                    "agent_id": agent["agent_id"],
                    "agent_name": agent["name"],
                    "team": agent["team"],
                    "channel": rng.choice(_CHANNELS),
                    "category": scenario["category"],
                    "transcript": scenario["sample_turns"],
                    "sentiment_score": round(max(-1.0, min(1.0, _jitter(rng, scenario["base_sentiment"], 0.12))), 2),
                    "handle_time_seconds": max(60, round(_jitter(rng, scenario["base_handle_time"], 50))),
                    "resolved": rng.random() < scenario["resolved_rate"],
                    "transfer_count": max(0, round(_jitter(rng, scenario["transfers"], 0.4))),
                    "knowledge_gap": True,
                    "knowledge_gap_category": scenario["category"],
                    "coaching_context": scenario["coaching_context"],
                    "escalation_threat": False,
                }
            )
            counter += 1
    rng.shuffle(interactions)
    return interactions


def generate_escalation_threat_interactions(seed: int = None) -> List[Dict[str, Any]]:
    """A small set of interactions where the customer explicitly threatened
    to escalate outside the contact center (regulator, ombudsman, consumer
    forum, legal action) - the raw material for Use Case 3's escalation-risk
    detection tool."""
    rng = random.Random((seed if seed is not None else settings.genesys_mock_seed) + 7777)
    interactions = []
    for i, scenario in enumerate(_ESCALATION_SCENARIOS):
        agent = _agent_by_id(scenario["agent_id"])
        interactions.append(
            {
                "interaction_id": f"ESC-{i + 1:04d}",
                "agent_id": agent["agent_id"],
                "agent_name": agent["name"],
                "team": agent["team"],
                "channel": rng.choice(_CHANNELS),
                "category": scenario["category"],
                "transcript": [f"Customer: {scenario['quote']}"],
                "sentiment_score": scenario["sentiment"],
                "handle_time_seconds": rng.randint(240, 420),
                "resolved": scenario["resolved"],
                "transfer_count": rng.choice([0, 1]),
                "knowledge_gap": False,
                "escalation_threat": True,
                "escalation_quote": scenario["quote"],
            }
        )
    return interactions


def generate_todays_full_interaction_log(seed: int = None) -> List[Dict[str, Any]]:
    """The union Use Case 3's 'review everything that happened today' tools
    draw from: the IVR/bot friction interactions Use Case 1 also sees, plus
    live-agent knowledge-gap interactions and escalation-threat interactions.
    Deliberately NOT fed into Use Case 1 (which only expects the 4 known
    IVR/bot flow/issue combinations in FLOWS)."""
    return (
        generate_interactions(seed)
        + generate_knowledge_gap_interactions(seed)
        + generate_escalation_threat_interactions(seed)
    )


def _jitter(rng: random.Random, base: float, spread: float) -> float:
    return base + rng.uniform(-spread, spread)


def generate_interactions(seed: int = None) -> List[Dict[str, Any]]:
    rng = random.Random(seed if seed is not None else settings.genesys_mock_seed)
    interactions = []
    counter = 1
    for scenario in _FRICTION_SCENARIOS:
        for _ in range(scenario["n"]):
            sentiment = round(max(-1.0, min(1.0, _jitter(rng, scenario["base_sentiment"], 0.15))), 2)
            handle_time = max(30, round(_jitter(rng, scenario["base_handle_time"], 60)))
            resolved = rng.random() < scenario["resolved_rate"]
            transfers = max(0, round(_jitter(rng, scenario["transfers"], 0.5)))
            interactions.append(
                {
                    "interaction_id": f"INT-{counter:04d}",
                    "channel": rng.choice(_CHANNELS),
                    "flow_name": scenario["flow_name"],
                    "issue_tag": scenario["issue_tag"],
                    "persona": rng.choice(_PERSONAS),
                    "transcript": scenario["sample_turns"],
                    "sentiment_score": sentiment,
                    "handle_time_seconds": handle_time,
                    "resolved": resolved,
                    "transfer_count": transfers,
                }
            )
            counter += 1
    rng.shuffle(interactions)
    return interactions


def generate_post_fix_interactions(
    flow_name: str,
    issue_tag: str,
    n: int,
    improvement_factor: float = 1.7,
    seed: int = None,
    baseline_stats: Dict[str, Any] = None,
) -> List[Dict[str, Any]]:
    """Simulate a fresh batch of interactions AFTER a fix has been deployed,
    used by the Measurement agent to validate real-world impact.

    If `baseline_stats` (the *actually observed* stats for the cluster being
    fixed) is provided, the improvement is computed relative to that real
    baseline rather than the static scenario design-time numbers - this
    keeps the "before" the Measurement agent sees consistent with the
    "after" it later generates, so the before/after comparison stays
    internally coherent even with small-sample randomness.
    """
    base_seed = (seed if seed is not None else settings.genesys_mock_seed) + 999
    # Independent RNG streams per attribute so that small-n draws for
    # "resolved" aren't positionally correlated with the other attributes'
    # draws (avoids misleading small-sample artifacts in the demo output).
    rng_misc = random.Random(base_seed)
    rng_resolved = random.Random(base_seed + 1)
    rng_sentiment = random.Random(base_seed + 2)
    rng_handle_time = random.Random(base_seed + 3)
    rng_transfers = random.Random(base_seed + 4)

    scenario = next(
        (s for s in _FRICTION_SCENARIOS if s["flow_name"] == flow_name and s["issue_tag"] == issue_tag), None
    )
    if scenario is None:
        scenario = _FRICTION_SCENARIOS[0]

    base_resolved_rate = baseline_stats["resolution_rate"] if baseline_stats else scenario["resolved_rate"]
    base_sentiment = baseline_stats["avg_sentiment"] if baseline_stats else scenario["base_sentiment"]
    base_handle_time = baseline_stats["avg_handle_time_seconds"] if baseline_stats else scenario["base_handle_time"]

    interactions = []
    new_resolved_rate = min(0.97, base_resolved_rate * improvement_factor)
    new_sentiment_base = min(0.9, base_sentiment + 0.6)
    new_handle_time_base = max(60, base_handle_time * 0.7)

    for i in range(n):
        interactions.append(
            {
                "interaction_id": f"POST-{i:04d}",
                "channel": rng_misc.choice(_CHANNELS),
                "flow_name": flow_name,
                "issue_tag": issue_tag,
                "persona": rng_misc.choice(_PERSONAS),
                "sentiment_score": round(max(-1, min(1, _jitter(rng_sentiment, new_sentiment_base, 0.15))), 2),
                "handle_time_seconds": max(30, round(_jitter(rng_handle_time, new_handle_time_base, 40))),
                "resolved": rng_resolved.random() < new_resolved_rate,
                "transfer_count": max(0, round(_jitter(rng_transfers, scenario["transfers"] * 0.5, 0.4))),
            }
        )
    return interactions


# ---------------------------------------------------------------------------
# Use Case 2 seed data: interactions that could NOT be resolved live and need
# a persistent autonomous follow-up agent. Tied to CRM customer IDs.
# ---------------------------------------------------------------------------
def generate_followup_candidate_interactions() -> List[Dict[str, Any]]:
    return [
        {
            "interaction_id": "FUP-0001",
            "customer_id": "CUST-1001",
            "channel": "voice",
            "issue_tag": "refund_pending_backoffice",
            "summary": "Customer requested a $128.40 refund for a duplicate charge; requires back-office finance approval.",
            "sentiment_score": -0.3,
            "resolved": False,
        },
        {
            "interaction_id": "FUP-0002",
            "customer_id": "CUST-1002",
            "channel": "chat",
            "issue_tag": "sim_swap_verification",
            "summary": "Customer needs a SIM swap approved; pending identity verification team review.",
            "sentiment_score": -0.1,
            "resolved": False,
        },
        {
            "interaction_id": "FUP-0003",
            "customer_id": "CUST-1003",
            "channel": "voice",
            "issue_tag": "installation_scheduling",
            "summary": "Customer needs a technician installation appointment scheduled by the field-ops team.",
            "sentiment_score": 0.05,
            "resolved": False,
        },
    ]


# ---------------------------------------------------------------------------
# Use Case 3 helper: "yesterday's" WFM snapshot (mock)
# ---------------------------------------------------------------------------
def generate_wfm_snapshot(seed: int = None) -> Dict[str, Any]:
    rng = random.Random((seed if seed is not None else settings.genesys_mock_seed) + 7)
    return {
        "scheduled_agents": 42,
        "actual_staffed_agents": 37,
        "shrinkage_pct": round(rng.uniform(8, 18), 1),
        "service_level_pct": round(rng.uniform(70, 92), 1),
        "avg_handle_time_seconds": round(rng.uniform(210, 310)),
        "occupancy_pct": round(rng.uniform(75, 95), 1),
    }
