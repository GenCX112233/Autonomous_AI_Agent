"""
Orchestrates Use Case 2: creates follow-up cases for interactions that
couldn't be resolved live, then simulates several "days" passing, on each
of which the persistent FollowUpOwnerAgent checks in on every open case -
exactly like a long-running background agent would in production.
"""
from typing import Any, Dict, List

from crm.client import CRMClient, ensure_crm_running
from llm.base import LLMClient
from mock_genesys.data import generate_followup_candidate_interactions
from usecase2_customer_followup.agents import (
    build_case_intake_agent,
    build_followup_owner_agent,
    run_intake,
    run_followup_tick,
)


class CustomerFollowUpOrchestrator:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        ensure_crm_running()
        self.crm = CRMClient()
        self.crm.reset()  # clean slate each demo run
        self.intake_agent = build_case_intake_agent(llm, self.crm)
        self.owner_agent = build_followup_owner_agent(llm, self.crm)

    def run(self, num_ticks: int = 5) -> None:
        print("\n=== USE CASE 2: Autonomous Customer Follow-Up ===")
        print(f"(sample CRM app running at {self.crm.base_url})")

        candidates = generate_followup_candidate_interactions()
        case_ids: List[str] = []
        for interaction in candidates:
            print(f"\n[Intake] Interaction {interaction['interaction_id']} for {interaction['customer_id']}: "
                  f"{interaction['summary']}")
            confirmation = run_intake(self.intake_agent, interaction)
            print(f"[Intake] {confirmation}")

        cases = self.crm.list_cases()
        case_ids = [c["case_id"] for c in cases]
        print(f"\n[Intake] {len(case_ids)} persistent follow-up case(s) opened: {case_ids}")

        for tick in range(1, num_ticks + 1):
            print(f"\n--- Day {tick}: backend teams work; follow-up agents check in ---")
            tick_result = self.crm.simulate_tick()
            if tick_result.get("changes"):
                for ch in tick_result["changes"]:
                    print(f"[Backend] {ch['ticket_id']} -> {ch['new_status']}")
            else:
                print("[Backend] No ticket status changes today.")

            open_cases = self.crm.list_cases(status="open")
            if not open_cases:
                print("[FollowUpOwnerAgent] All cases resolved and closed. Nothing left to own.")
                break

            for case in open_cases:
                trace = run_followup_tick(self.owner_agent, case["case_id"])
                actions = [t["name"] for t in trace.transcript if "name" in t]
                print(f"[FollowUpOwnerAgent] {case['case_id']}: actions={actions} -> {trace.final_text}")

        self._print_final_summary()

    def _print_final_summary(self):
        print("\n--- Final case summary ---")
        for case in self.crm.list_cases():
            print(f"  {case['case_id']} [{case['status']}] customer={case['customer_id']} "
                  f"ticket={case['ticket_id']} notes={case['notes']}")

        print("\n--- Customer communications log ---")
        for comm in self.crm.list_communications():
            print(f"  day {comm['tick']} | {comm['case_id']} -> {comm['customer_id']} "
                  f"[{comm['update_type']}]: {comm['message']}")
