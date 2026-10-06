"""
Orchestrates the Use Case 1 multi-agent pipeline end to end, and implements
the human-in-the-loop supervisor gate: nothing gets "deployed" without
explicit approval (or --auto-approve for unattended demos/CI).
"""
from typing import Any, Dict, List

from config import settings
from llm.base import LLMClient
from mock_genesys.data import generate_interactions, generate_post_fix_interactions, FLOWS
from usecase1_cx_optimization.agents import (
    SignalMiningSwarm,
    RootCauseAgent,
    FixAgent,
    AdversarialSimulationSwarm,
    ComplianceAgent,
    MeasurementAgent,
    compute_stats,
    apply_fix_to_flow_registry,
)


class CXOptimizationOrchestrator:
    def __init__(self, llm: LLMClient, auto_approve: bool = None):
        self.llm = llm
        self.auto_approve = settings.auto_approve if auto_approve is None else auto_approve
        self.signal_mining = SignalMiningSwarm(llm)
        self.root_cause = RootCauseAgent(llm)
        self.fixer = FixAgent(llm)
        self.simulator = AdversarialSimulationSwarm(llm)
        self.compliance = ComplianceAgent(llm)
        self.measurement = MeasurementAgent(llm)

    def run(self, top_n: int = 2) -> List[Dict[str, Any]]:
        print("\n=== USE CASE 1: Autonomous CX Optimization ===")
        interactions = generate_interactions()
        print(f"[Detect] Pulled {len(interactions)} synthetic interactions from mock Genesys Cloud.")

        clusters = self.signal_mining.analyze(interactions)
        print(f"[Detect] Signal-mining swarm found {len(clusters)} friction clusters.")
        for c in clusters:
            print(f"    - {c['flow_name']}/{c['issue_tag']}: priority={c.get('priority_score')} "
                  f"impact={c.get('customer_impact')} (n={c['stats']['count']})")

        results = []
        for cluster in clusters[:top_n]:
            results.append(self._process_cluster(cluster))
        return results

    def _process_cluster(self, cluster: Dict[str, Any]) -> Dict[str, Any]:
        flow_name, issue_tag = cluster["flow_name"], cluster["issue_tag"]
        print(f"\n--- Processing cluster: {flow_name}/{issue_tag} ---")

        # Diagnose
        root_cause = self.root_cause.diagnose(cluster)
        print(f"[Diagnose] Root cause: {root_cause.get('root_cause_explanation')}")

        # Fix
        fix = self.fixer.propose(cluster, root_cause)
        print(f"[Fix] Proposed change: {fix.get('change_description')}")

        # Simulate
        simulation = self.simulator.simulate(cluster, fix)
        agg = simulation["aggregate"]
        print(
            "[Simulate] Avg across personas -> resolution: "
            f"{agg['old']['resolution_likelihood']} -> {agg['new']['resolution_likelihood']}, "
            f"effort: {agg['old']['effort_score_1_5']} -> {agg['new']['effort_score_1_5']}, "
            f"frustration: {agg['old']['frustration_score_1_5']} -> {agg['new']['frustration_score_1_5']}"
        )

        # Compliance
        compliance_result = self.compliance.check(fix, cluster)
        print(f"[Compliance] Verdict: {compliance_result.get('verdict')} (risk={compliance_result.get('risk_level')})")

        # Approve (human-in-the-loop supervisor gate)
        approved = self._supervisor_gate(cluster, root_cause, fix, simulation, compliance_result)
        if not approved:
            print("[Approve] Supervisor rejected the change. Skipping deployment.")
            return {
                "cluster": cluster, "root_cause": root_cause, "fix": fix,
                "simulation": simulation, "compliance": compliance_result,
                "approved": False,
            }

        # Deploy
        apply_fix_to_flow_registry(flow_name, fix["proposed_flow_steps"])
        print(f"[Deploy] Flow '{flow_name}' updated in Architect (simulated).")

        # Measure
        before_stats = cluster["stats"]
        post_fix_interactions = generate_post_fix_interactions(
            flow_name, issue_tag, n=max(40, before_stats["count"] * 2), baseline_stats=before_stats
        )
        after_stats = compute_stats(post_fix_interactions)
        measurement = self.measurement.measure(before_stats, after_stats)
        print(f"[Measure] {measurement.get('impact_summary')}")
        print(f"[Measure] Recommendation: {measurement.get('recommendation')}")

        return {
            "cluster": cluster, "root_cause": root_cause, "fix": fix,
            "simulation": simulation, "compliance": compliance_result,
            "approved": True, "before_stats": before_stats, "after_stats": after_stats,
            "measurement": measurement,
        }

    def _supervisor_gate(self, cluster, root_cause, fix, simulation, compliance_result) -> bool:
        print("\n[Approve] --- Supervisor review packet ---")
        print(f"  Cluster:      {cluster['flow_name']} / {cluster['issue_tag']}")
        print(f"  Root cause:   {root_cause.get('root_cause_explanation')}")
        print(f"  Proposed fix: {fix.get('change_description')}")
        print(f"  Compliance:   {compliance_result.get('verdict')} (risk={compliance_result.get('risk_level')})")
        if compliance_result.get("violations"):
            print(f"  Violations:   {compliance_result['violations']}")
        agg = simulation["aggregate"]
        print(
            f"  Simulated resolution lift: {agg['old']['resolution_likelihood']} -> "
            f"{agg['new']['resolution_likelihood']}"
        )

        if compliance_result.get("verdict") == "FLAGGED":
            print("[Approve] Auto-rejecting: compliance flagged this change.")
            return False

        if self.auto_approve:
            print("[Approve] AUTO_APPROVE is enabled - approving without a human prompt.")
            return True

        try:
            answer = input("Approve and deploy this change? [y/N]: ").strip().lower()
        except EOFError:
            answer = ""
        return answer == "y"
