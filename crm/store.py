"""
A tiny persistence layer for the sample CRM application.

Deliberately dependency-light (plain JSON file instead of a real DB) since
this CRM exists to give the Use Case 2 follow-up agents something real to
call - not to be a production data layer. Swap this for Postgres/etc. in a
real deployment without touching crm/app.py's route logic much.
"""
import json
import os
import random
import threading
from typing import Any, Dict, List, Optional

from config import settings

_lock = threading.Lock()


def _default_state() -> Dict[str, Any]:
    return {
        "customers": {},
        "cases": {},
        "tickets": {},
        "communications": [],
        "_next_case_id": 1,
        "_next_ticket_id": 1,
    }


class CRMStore:
    def __init__(self, path: str = None):
        self.path = path or settings.crm_data_file
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.state = self._load()
        # A single persistent RNG stream for the "backend world" simulation.
        # Deliberately NOT re-seeded per call: re-seeding from something like
        # hash((path, len(tickets))) would draw the exact same "did this
        # ticket progress?" outcome every tick once the ticket count
        # stabilizes, silently freezing all tickets forever. Seeding once
        # here keeps the whole run reproducible (same seed => same story
        # every demo run) while still genuinely advancing tick to tick.
        self._rng = random.Random(settings.genesys_mock_seed + 1234)

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                return json.load(f)
        return _default_state()

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.state, f, indent=2)

    def reset(self):
        with _lock:
            self.state = _default_state()
            self._rng = random.Random(settings.genesys_mock_seed + 1234)
            self._save()

    # ---------------- customers ----------------
    def upsert_customer(self, customer_id: str, name: str, email: str, phone: str):
        with _lock:
            self.state["customers"][customer_id] = {
                "customer_id": customer_id,
                "name": name,
                "email": email,
                "phone": phone,
            }
            self._save()

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return self.state["customers"].get(customer_id)

    def list_customers(self) -> List[Dict[str, Any]]:
        return list(self.state["customers"].values())

    # ---------------- cases ----------------
    def create_case(self, customer_id: str, summary: str, category: str, priority: str = "normal") -> Dict[str, Any]:
        with _lock:
            case_id = f"CASE-{self.state['_next_case_id']:04d}"
            self.state["_next_case_id"] += 1
            case = {
                "case_id": case_id,
                "customer_id": customer_id,
                "summary": summary,
                "category": category,
                "priority": priority,
                "status": "open",
                "ticket_id": None,
                "notes": [],
                "tick": 0,
            }
            self.state["cases"][case_id] = case
            self._save()
            return case

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self.state["cases"].get(case_id)

    def list_cases(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        cases = list(self.state["cases"].values())
        if status:
            cases = [c for c in cases if c["status"] == status]
        return cases

    def add_case_note(self, case_id: str, note: str) -> Dict[str, Any]:
        with _lock:
            case = self.state["cases"][case_id]
            case["notes"].append(note)
            self._save()
            return case

    def close_case(self, case_id: str) -> Dict[str, Any]:
        with _lock:
            case = self.state["cases"][case_id]
            case["status"] = "closed"
            self._save()
            return case

    # ---------------- tickets (simulated backend/back-office systems) ----------------
    def create_ticket(self, case_id: str, summary: str) -> Dict[str, Any]:
        with _lock:
            ticket_id = f"TCK-{self.state['_next_ticket_id']:04d}"
            self.state["_next_ticket_id"] += 1
            ticket = {
                "ticket_id": ticket_id,
                "case_id": case_id,
                "summary": summary,
                "status": "pending",  # pending -> in_progress -> resolved
                "priority": "normal",
                "ticks_since_update": 0,
                "escalated": False,
            }
            self.state["tickets"][ticket_id] = ticket
            self.state["cases"][case_id]["ticket_id"] = ticket_id
            self._save()
            return ticket

    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        return self.state["tickets"].get(ticket_id)

    def escalate_ticket(self, ticket_id: str, reason: str) -> Dict[str, Any]:
        with _lock:
            ticket = self.state["tickets"][ticket_id]
            ticket["escalated"] = True
            ticket["priority"] = "high"
            ticket.setdefault("escalation_reasons", []).append(reason)
            self._save()
            return ticket

    # ---------------- customer communications ----------------
    def log_communication(self, case_id: str, customer_id: str, message: str, update_type: str) -> Dict[str, Any]:
        with _lock:
            entry = {
                "case_id": case_id,
                "customer_id": customer_id,
                "message": message,
                "update_type": update_type,
                "tick": self.state["cases"].get(case_id, {}).get("tick", 0),
            }
            self.state["communications"].append(entry)
            self._save()
            return entry

    def list_communications(self, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
        comms = self.state["communications"]
        if case_id:
            comms = [c for c in comms if c["case_id"] == case_id]
        return comms

    # ---------------- world simulation ----------------
    def simulate_tick(self, seed_offset: int = 0) -> Dict[str, Any]:
        """Simulates one 'day' passing: the back-office / backend teams make
        (probabilistic) progress on open tickets. Escalated / high-priority
        tickets are more likely to move. This is what stands in for real
        backend systems in the hackathon demo."""
        with _lock:
            rng = self._rng
            changes = []
            for ticket in self.state["tickets"].values():
                if ticket["status"] == "resolved":
                    continue
                ticket["ticks_since_update"] += 1
                progress_chance = 0.65 if ticket["priority"] == "high" else 0.40
                if rng.random() < progress_chance:
                    if ticket["status"] == "pending":
                        ticket["status"] = "in_progress"
                    elif ticket["status"] == "in_progress":
                        ticket["status"] = "resolved"
                    ticket["ticks_since_update"] = 0
                    changes.append({"ticket_id": ticket["ticket_id"], "new_status": ticket["status"]})
            for case in self.state["cases"].values():
                case["tick"] = case.get("tick", 0) + 1
            self._save()
            return {"changes": changes}
