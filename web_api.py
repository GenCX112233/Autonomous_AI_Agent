"""Local demo API for the React UI. The original CLI remains available."""
import copy
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from crm.client import CRMClient, ensure_crm_running
from llm.factory import get_llm_client
from mock_genesys.data import FLOWS, generate_interactions, generate_followup_candidate_interactions, generate_post_fix_interactions, generate_wfm_snapshot
from usecase1_cx_optimization.agents import apply_fix_to_flow_registry, compute_stats
from usecase1_cx_optimization.orchestrator import CXOptimizationOrchestrator
from usecase2_customer_followup.agents import build_case_intake_agent, build_followup_owner_agent, run_intake, run_followup_tick
from usecase3_autonomous_supervisor.agents import answer_supervisor_question

app = FastAPI(title="CX Autopilot Demo API")
_lock = threading.RLock()
_original_flows = copy.deepcopy(FLOWS)
_clusters = []
_proposals = {}
_events = []
_day = 0


@app.on_event("startup")
def _startup():
    # Start the CRM immediately when this app boots, rather than lazily on
    # the first Customer Follow-up API call. Browsing straight to the CRM's
    # own dashboard (http://<host>:8001) before ever touching Use Case 2 in
    # the UI would otherwise find nothing listening on that port yet.
    # Caught rather than raised: a CRM startup problem (e.g. port 8001 is
    # already in use by something else) shouldn't take down Use Cases 1 and
    # 3, which don't depend on the CRM at all.
    try:
        ensure_crm_running()
    except Exception as exc:
        print(f"[startup] CRM did not start automatically: {exc}")
        print("[startup] Use Cases 1 and 3 are unaffected. For Use Case 2, "
              "start the CRM manually: python -m uvicorn crm.app:app --host 0.0.0.0 --port 8001")


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class Decision(BaseModel):
    approved: bool


def _crm():
    ensure_crm_running()
    return CRMClient()


def _followup_state(crm):
    cases = crm.list_cases()
    customers = {c["customer_id"]: c for c in crm.list_customers()}
    tickets = {c["ticket_id"]: crm.get_ticket_status(c["ticket_id"]) for c in cases if c["ticket_id"]}
    return {"day": _day, "cases": cases, "customers": customers, "tickets": tickets,
            "communications": crm.list_communications(), "events": _events[-60:]}


@app.get("/api/overview")
def overview():
    interactions = generate_interactions()
    llm = get_llm_client()
    return {"provider": llm.name, "model": getattr(llm, "model", None) or llm.name,
            "source": "Synthetic Genesys Cloud data",
            "stats": compute_stats(interactions), "interactions": len(interactions),
            "flows": len(FLOWS), "wfm": generate_wfm_snapshot(),
            "proposals": len(_proposals)}


@app.get("/api/optimization")
def optimization_state():
    with _lock:
        return {"clusters": _clusters, "proposals": list(_proposals.values())}


@app.post("/api/optimization/scan")
def scan():
    global _clusters
    with _lock:
        FLOWS.clear()
        FLOWS.update(copy.deepcopy(_original_flows))
        _proposals.clear()
        llm = get_llm_client()
        _clusters = CXOptimizationOrchestrator(llm).signal_mining.analyze(generate_interactions())
        return {"clusters": _clusters, "proposals": []}


@app.post("/api/optimization/proposals/{issue_tag}")
def propose(issue_tag: str):
    with _lock:
        cluster = next((c for c in _clusters if c["issue_tag"] == issue_tag), None)
        if not cluster:
            raise HTTPException(404, "Run the signal scan and select a discovered issue")
        if issue_tag in _proposals:
            return _proposals[issue_tag]
        pipeline = CXOptimizationOrchestrator(get_llm_client())
        old_steps = copy.deepcopy(FLOWS[cluster["flow_name"]])
        root = pipeline.root_cause.diagnose(cluster)
        fix = pipeline.fixer.propose(cluster, root)
        simulation = pipeline.simulator.simulate(cluster, fix)
        compliance = pipeline.compliance.check(fix, cluster)
        packet = {"id": issue_tag, "cluster": cluster, "root_cause": root, "fix": fix,
                  "old_steps": old_steps, "simulation": simulation, "compliance": compliance,
                  "status": "awaiting_approval" if compliance.get("verdict") != "FLAGGED" else "compliance_blocked"}
        _proposals[issue_tag] = packet
        return packet


@app.post("/api/optimization/proposals/{issue_tag}/decision")
def decide(issue_tag: str, decision: Decision):
    with _lock:
        packet = _proposals.get(issue_tag)
        if not packet:
            raise HTTPException(404, "Proposal not found")
        if packet["status"] != "awaiting_approval":
            raise HTTPException(409, "This proposal is no longer awaiting approval")
        if not decision.approved:
            packet["status"] = "rejected"
            return packet
        if packet["compliance"].get("verdict") == "FLAGGED":
            raise HTTPException(409, "Compliance blocked deployment")
        cluster = packet["cluster"]
        apply_fix_to_flow_registry(cluster["flow_name"], packet["fix"]["proposed_flow_steps"])
        before = cluster["stats"]
        after = compute_stats(generate_post_fix_interactions(
            cluster["flow_name"], cluster["issue_tag"], n=max(40, before["count"] * 2), baseline_stats=before))
        packet.update(status="deployed", before_stats=before, after_stats=after,
                      measurement=CXOptimizationOrchestrator(get_llm_client()).measurement.measure(before, after))
        return packet


@app.get("/api/followup")
def followup_state():
    with _lock:
        return _followup_state(_crm())


@app.post("/api/followup/start")
def start_followup():
    global _day
    with _lock:
        crm = _crm()
        crm.reset()
        _events.clear()
        _day = 0
        agent = build_case_intake_agent(get_llm_client(), crm)
        for interaction in generate_followup_candidate_interactions():
            confirmation = run_intake(agent, interaction)
            _events.append({"day": 0, "type": "intake", "detail": confirmation,
                            "interaction_id": interaction["interaction_id"]})
        return _followup_state(crm)


@app.post("/api/followup/tick")
def tick_followup():
    global _day
    with _lock:
        crm = _crm()
        if not crm.list_cases():
            raise HTTPException(409, "Start a follow-up run first")
        if not crm.list_cases(status="open"):
            return _followup_state(crm)
        _day += 1
        changes = crm.simulate_tick()["changes"]
        for change in changes:
            _events.append({"day": _day, "type": "backend", "detail": f"{change['ticket_id']} → {change['new_status']}"})
        owner = build_followup_owner_agent(get_llm_client(), crm)
        for case in crm.list_cases(status="open"):
            trace = run_followup_tick(owner, case["case_id"])
            actions = [item["name"] for item in trace.transcript if "name" in item]
            _events.append({"day": _day, "type": "agent", "case_id": case["case_id"],
                            "actions": actions, "detail": trace.final_text})
        return _followup_state(crm)


@app.post("/api/supervisor/ask")
def ask(question: Question):
    return answer_supervisor_question(get_llm_client(), question.question.strip())


# When built, a single Python process can serve the UI and API at port 8000.
from pathlib import Path
_dist = Path(__file__).parent / "web" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        return FileResponse(_dist / "index.html")
