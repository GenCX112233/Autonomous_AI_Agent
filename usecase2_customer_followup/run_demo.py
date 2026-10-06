"""
Run: python -m usecase2_customer_followup.run_demo

This will auto-start the sample CRM app (crm/app.py) on 127.0.0.1:8001 in a
background thread unless it's already running (e.g. started separately with
`uvicorn crm.app:app --port 8001`, which better reflects "another application").
"""
from llm.factory import get_llm_client
from usecase2_customer_followup.orchestrator import CustomerFollowUpOrchestrator


def main():
    llm = get_llm_client()
    print(f"(LLM backend: {llm.name})")
    orchestrator = CustomerFollowUpOrchestrator(llm)
    orchestrator.run(num_ticks=5)


if __name__ == "__main__":
    main()
