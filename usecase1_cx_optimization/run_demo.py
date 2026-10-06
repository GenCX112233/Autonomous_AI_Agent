"""
Run: python -m usecase1_cx_optimization.run_demo
"""
from llm.factory import get_llm_client
from usecase1_cx_optimization.orchestrator import CXOptimizationOrchestrator


def main():
    llm = get_llm_client()
    print(f"(LLM backend: {llm.name})")
    orchestrator = CXOptimizationOrchestrator(llm)
    orchestrator.run(top_n=2)


if __name__ == "__main__":
    main()
