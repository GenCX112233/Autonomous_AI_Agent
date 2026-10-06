from crm.store import CRMStore

SAMPLE_CUSTOMERS = [
    {"customer_id": "CUST-1001", "name": "Priya Nair", "email": "priya.nair@example.com", "phone": "+91-98100-11223"},
    {"customer_id": "CUST-1002", "name": "Daniel Kim", "email": "daniel.kim@example.com", "phone": "+1-415-555-0182"},
    {"customer_id": "CUST-1003", "name": "Amara Okafor", "email": "amara.okafor@example.com", "phone": "+44-7700-900321"},
]


def seed(store: CRMStore, reset: bool = True):
    if reset:
        store.reset()
    for c in SAMPLE_CUSTOMERS:
        store.upsert_customer(**c)
