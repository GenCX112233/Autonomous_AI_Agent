"""
Run: python -m usecase3_autonomous_supervisor.run_demo
"""
from llm.factory import get_llm_client
from usecase3_autonomous_supervisor.agents import answer_supervisor_question

SAMPLE_QUESTIONS = [
    "What were the major customer issues today?",
    "Why might average handling time be increasing?",
    "Review all of today's interactions: identify issues, coach agents on knowledge gaps, "
    "and flag any escalation threats.",
]


def main():
    llm = get_llm_client()
    print(f"(LLM backend: {llm.name})")
    print("\n=== USE CASE 3: Autonomous Supervisor - Ask Your Contact Center ===")
    for question in SAMPLE_QUESTIONS:
        print(f"\nSupervisor asks: \"{question}\"")
        result = answer_supervisor_question(llm, question)
        print(f"[Plan] {result['plan'].get('analysis_plan')}")
        print(f"[Report]\n{result['report'].get('report')}")
        recs = result['report'].get('recommended_investigation', [])
        if recs:
            print("[Recommended investigation]")
            for r in recs:
                print(f"  - {r}")
        coaching = result['report'].get('coaching_recommendations', [])
        if coaching:
            print("[Coaching recommendations]")
            for c in coaching:
                print(f"  - {c['agent_name']} ({c['team']}) - {c['knowledge_gap']}: {c['recommendation']}")
        escalations = result['report'].get('escalation_alerts', [])
        if escalations:
            print("[Escalation alerts]")
            for e in escalations:
                print(f"  - {e['interaction_id']} [{e['severity']}] \"{e['customer_quote']}\" -> {e['recommended_action']}")


if __name__ == "__main__":
    main()
