"""
CX Autopilot - hackathon demo entry point.

Usage:
    python main.py 1        # Use Case 1: Autonomous CX Optimization
    python main.py 2        # Use Case 2: Autonomous Customer Follow-Up (+ sample CRM)
    python main.py 3        # Use Case 3: Autonomous Supervisor
    python main.py all      # Run all three, in order

LLM backend is controlled entirely by config.py / .env (LLM_PROVIDER=
anthropic|openai|mock). No code changes needed to switch models.
"""
import sys


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"

    if which in ("1", "all"):
        from usecase1_cx_optimization.run_demo import main as run1
        run1()

    if which in ("2", "all"):
        from usecase2_customer_followup.run_demo import main as run2
        run2()

    if which in ("3", "all"):
        from usecase3_autonomous_supervisor.run_demo import main as run3
        run3()

    if which not in ("1", "2", "3", "all"):
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
