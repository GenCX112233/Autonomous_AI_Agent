"""
Thin HTTP client for the sample CRM application. Agents call these methods
(wrapped as Tools - see usecase2_customer_followup/agents.py) exactly like
they would call a real CRM/ticketing REST API.
"""
import threading
import time
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import requests

from config import settings


_startup_lock = threading.Lock()


class CRMClient:
    def __init__(self, base_url: str = None):
        self.base_url = (base_url or settings.crm_base_url).rstrip("/")

    def _get(self, path: str, **params) -> Any:
        r = requests.get(f"{self.base_url}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        r = requests.post(f"{self.base_url}{path}", json=body or {}, timeout=10)
        r.raise_for_status()
        return r.json()

    # ---- customers ----
    def get_customer(self, customer_id: str) -> Any:
        return self._get(f"/customers/{customer_id}")

    def list_customers(self) -> Any:
        return self._get("/customers")

    # ---- cases ----
    def create_case(self, customer_id: str, summary: str, category: str, priority: str = "normal") -> Any:
        return self._post("/cases", {"customer_id": customer_id, "summary": summary, "category": category, "priority": priority})

    def get_case(self, case_id: str) -> Any:
        return self._get(f"/cases/{case_id}")

    def list_cases(self, status: Optional[str] = None) -> Any:
        return self._get("/cases", **({"status": status} if status else {}))

    def add_case_note(self, case_id: str, note: str) -> Any:
        return self._post(f"/cases/{case_id}/notes", {"note": note})

    def close_case(self, case_id: str) -> Any:
        return self._post(f"/cases/{case_id}/close")

    # ---- tickets ----
    def create_ticket(self, case_id: str, summary: str) -> Any:
        return self._post("/tickets", {"case_id": case_id, "summary": summary})

    def get_ticket_status(self, ticket_id: str) -> Any:
        return self._get(f"/tickets/{ticket_id}")

    def escalate_ticket(self, ticket_id: str, reason: str) -> Any:
        return self._post(f"/tickets/{ticket_id}/escalate", {"reason": reason})

    # ---- customer communications ----
    def send_customer_update(self, case_id: str, message: str, update_type: str = "progress") -> Any:
        case = self.get_case(case_id)
        return self._post(
            f"/cases/{case_id}/communications",
            {"customer_id": case["customer_id"], "message": message, "update_type": update_type},
        )

    def list_communications(self, case_id: Optional[str] = None) -> Any:
        return self._get("/communications", **({"case_id": case_id} if case_id else {}))

    # ---- world simulation ----
    def simulate_tick(self) -> Any:
        return self._post("/simulate/tick")

    def reset(self) -> Any:
        return self._post("/admin/reset")

    def wait_until_healthy(self, timeout: float = 10.0):
        deadline = time.time() + timeout
        last_err = None
        while time.time() < deadline:
            try:
                r = requests.get(f"{self.base_url}/health", timeout=1)
                if r.status_code == 200:
                    return True
            except Exception as exc:
                last_err = exc
            time.sleep(0.3)
        raise RuntimeError(f"CRM app never became healthy at {self.base_url}: {last_err}")


def ensure_crm_running():
    """If AUTO_START_CRM is enabled and nothing answers at CRM_BASE_URL yet,
    boot the FastAPI app and bind it to all local interfaces (0.0.0.0).

    Binding to all interfaces - rather than only 127.0.0.1 when CRM_BASE_URL
    happens to be localhost - means the CRM is reachable both from inside
    this process (via whatever CRM_BASE_URL is configured, since 0.0.0.0
    also answers on 127.0.0.1) and from a browser hitting this machine's
    WSL/LAN IP directly, without requiring CRM_BASE_URL to be changed to
    match. WSL IPs also change across restarts, so not depending on that
    value for the bind address is more robust.
    """
    with _startup_lock:
        client = CRMClient()
        try:
            client.wait_until_healthy(timeout=1.5)
            return  # already running (e.g. started separately with uvicorn)
        except Exception:
            pass

        if not settings.auto_start_crm:
            raise RuntimeError(
                f"CRM app is not running at {settings.crm_base_url}. Start it with:\n"
                f"  python -m uvicorn crm.app:app --host 0.0.0.0 --port 8001\n"
                f"or set AUTO_START_CRM=true."
            )

        address = urlsplit(client.base_url)
        if address.scheme != "http" or not address.hostname or address.path not in ("", "/"):
            raise RuntimeError("AUTO_START_CRM requires CRM_BASE_URL to be an http://host:port URL")
        port = address.port or 80

        import uvicorn

        def _run():
            uvicorn.run("crm.app:app", host="0.0.0.0", port=port, log_level="warning")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        try:
            client.wait_until_healthy(timeout=15.0)
        except RuntimeError as exc:
            raise RuntimeError(
                f"CRM failed to start on port {port}. Confirm nothing else is using that port, "
                f"and that CRM_BASE_URL ({settings.crm_base_url}) points at host-reachable address."
            ) from exc
