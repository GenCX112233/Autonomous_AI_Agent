"""
Sample CRM application.

This is a genuinely separate application (its own FastAPI service, its own
data store) that the Use Case 2 autonomous follow-up agents talk to over
HTTP, the same way they'd talk to a real CRM/ticketing system. Run it with:

    uvicorn crm.app:app --port 8001

or let usecase2_customer_followup/run_demo.py auto-start it in-process.

Visiting http://127.0.0.1:8001/ in a browser shows a small read-only ops
dashboard (crm/static/index.html) that polls this same REST API - useful for
a live demo, so you can show the agent's actions landing in "the CRM" in a
separate window/tab rather than only inside the main agent UI.
"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from crm.store import CRMStore
from crm.seed import seed

app = FastAPI(title="Sample CRM & Ticketing System", version="1.0")
store = CRMStore()

_STATIC_DIR = Path(__file__).parent / "static"


@app.on_event("startup")
def _startup():
    # Seed with sample customers if the store is empty.
    if not store.list_customers():
        seed(store, reset=False)


@app.get("/")
def dashboard():
    """The CRM's own read-only ops dashboard - a separate visual surface
    from the main agent UI, so a demo can show both side by side."""
    return FileResponse(_STATIC_DIR / "index.html")


# ---------------------------------------------------------------------- #
# Schemas
# ---------------------------------------------------------------------- #
class CreateCaseRequest(BaseModel):
    customer_id: str
    summary: str
    category: str
    priority: str = "normal"


class CreateTicketRequest(BaseModel):
    case_id: str
    summary: str


class EscalateTicketRequest(BaseModel):
    reason: str


class NoteRequest(BaseModel):
    note: str


class CustomerUpdateRequest(BaseModel):
    customer_id: str
    message: str
    update_type: str = "progress"


# ---------------------------------------------------------------------- #
# Customers
# ---------------------------------------------------------------------- #
@app.get("/customers")
def list_customers():
    return store.list_customers()


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    c = store.get_customer(customer_id)
    if not c:
        raise HTTPException(404, "Customer not found")
    return c


# ---------------------------------------------------------------------- #
# Cases
# ---------------------------------------------------------------------- #
@app.post("/cases")
def create_case(req: CreateCaseRequest):
    if not store.get_customer(req.customer_id):
        raise HTTPException(404, f"Unknown customer_id {req.customer_id}")
    return store.create_case(req.customer_id, req.summary, req.category, req.priority)


@app.get("/cases")
def list_cases(status: Optional[str] = None):
    return store.list_cases(status)


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    c = store.get_case(case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    return c


@app.post("/cases/{case_id}/notes")
def add_note(case_id: str, req: NoteRequest):
    if not store.get_case(case_id):
        raise HTTPException(404, "Case not found")
    return store.add_case_note(case_id, req.note)


@app.post("/cases/{case_id}/close")
def close_case(case_id: str):
    if not store.get_case(case_id):
        raise HTTPException(404, "Case not found")
    return store.close_case(case_id)


# ---------------------------------------------------------------------- #
# Tickets (stand-in for backend / back-office systems)
# ---------------------------------------------------------------------- #
@app.post("/tickets")
def create_ticket(req: CreateTicketRequest):
    if not store.get_case(req.case_id):
        raise HTTPException(404, "Case not found")
    return store.create_ticket(req.case_id, req.summary)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    t = store.get_ticket(ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    # Convenience field for agents: is this ticket stalled past a threshold?
    result = dict(t)
    result["is_stalled"] = t["status"] != "resolved" and t["ticks_since_update"] >= 2
    return result


@app.post("/tickets/{ticket_id}/escalate")
def escalate_ticket(ticket_id: str, req: EscalateTicketRequest):
    if not store.get_ticket(ticket_id):
        raise HTTPException(404, "Ticket not found")
    return store.escalate_ticket(ticket_id, req.reason)


# ---------------------------------------------------------------------- #
# Customer communications log (what the agent proactively sent, and when)
# ---------------------------------------------------------------------- #
@app.post("/cases/{case_id}/communications")
def log_communication(case_id: str, req: CustomerUpdateRequest):
    if not store.get_case(case_id):
        raise HTTPException(404, "Case not found")
    return store.log_communication(case_id, req.customer_id, req.message, req.update_type)


@app.get("/communications")
def list_communications(case_id: Optional[str] = None):
    return store.list_communications(case_id)


# ---------------------------------------------------------------------- #
# World simulation - stands in for the real backend/back-office teams
# making (probabilistic) progress on tickets between agent check-ins.
# ---------------------------------------------------------------------- #
@app.post("/simulate/tick")
def simulate_tick():
    return store.simulate_tick()


@app.post("/admin/reset")
def admin_reset():
    seed(store, reset=True)
    return {"status": "reset"}


@app.get("/health")
def health():
    return {"status": "ok"}
