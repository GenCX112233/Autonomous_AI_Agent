# CX Autopilot

A multi-agent implementation of the **Autonomous AI Agent** hackathon idea: autonomous AI
agents that sit alongside Genesys Cloud and continuously discover, fix, validate,
and follow up on contact-center problems - instead of waiting for a human to
notice them.

This repo implements all three use cases from the vision doc:

1. **Autonomous CX Optimization** - Discover, Fix, Validate & Improve
2. **Autonomous Customer Follow-Up** - Own the Issue Until Resolution (with a
   real unified CRM application the agents call)
3. **Autonomous Supervisor** - Ask Your Contact Center

Every agent is powered by the **same configurable LLM layer** - flip one setting
to switch the whole system between **Claude**, **GPT**, or an **open source LLM
model**

## React demo UI

The React dashboard runs the existing Python agents through a local FastAPI
adapter. It has an overview, interactive optimization review, a persistent
follow-up case board, and a conversational supervisor report. The bundled
`web/dist` is prebuilt, so Python is all you need to run the UI:

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # optional: mock is the default
python -m uvicorn web_api:app --host 0.0.0.0 --port 8000
```

Open **http://127.0.0.1:8000**. The sample CRM now starts automatically as
soon as this process boots (not lazily on first use), and always binds to
all local interfaces, so it's reachable the same way the main app is. Open a
second browser tab/window on **http://127.0.0.1:8001** for the CRM's own
live ops dashboard - the same case/ticket/communication state the agents are
changing, reflected in a visually separate application, which is the
clearest way to show a jury this is a real integration and not just one UI
narrating itself. The CRM's raw API/Swagger docs stay at
`http://127.0.0.1:8001/docs`.
The original `python main.py 1|2|3|all` commands still work.

### Running inside WSL

If you're browsing from Windows (or any machine other than the one running
the server) and `localhost`/`127.0.0.1` doesn't reach it, start **both**
services bound to all interfaces and browse via the WSL instance's IP for
both ports:

```bash
python -m uvicorn web_api:app --host 0.0.0.0 --port 8000
```

- Find the current WSL IP with `hostname -I` (it can change after a
  restart). Then open `http://<that-ip>:8000` and, for the CRM,
  `http://<that-ip>:8001`.
- The CRM no longer needs `CRM_BASE_URL` changed to match - it always binds
  `0.0.0.0` regardless of that setting, so `http://localhost:8001`,
  `http://127.0.0.1:8001`, and `http://<wsl-ip>:8001` all work once the main
  app has started.
- If `http://localhost:8000` (or `:8001`) still doesn't load from Windows
  even though WSL2 normally forwards localhost automatically, check Windows
  Defender Firewall isn't blocking the "WSL" / "vEthernet" adapter for
  inbound connections on 8000/8001, and confirm nothing else on either
  machine is already using those ports.
- If only the CRM fails to come up, the main dashboard still works - Use
  Cases 1 and 3 don't depend on the CRM. Check the terminal running
  `uvicorn web_api:app` for a `[startup] CRM did not start automatically: ...`
  line, which explains why, and start it by hand with
  `python -m uvicorn crm.app:app --host 0.0.0.0 --port 8001` in a separate
  terminal.

For React development (Node.js 20.19+ or 22.12+):

```bash
cd web
npm ci
npm run dev                # http://127.0.0.1:5173, proxies /api to :8000
npm run build              # updates web/dist served by Python
```

Run the Python API in another terminal for development.

### GPT-6 Luna configuration

For the OpenAI backend, set these values in your own `.env` file and restart
the Python server:

```dotenv
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-6-luna
OPENAI_API_KEY=your-api-key
```

The existing adapter uses Chat Completions. It sets
`reasoning_effort="none"` on Luna requests with functions (case intake,
follow-up, and supervisor analytics), as required for that API combination.
The analysis agents without functions retain Luna's default reasoning.
Existing prompts work without a model-specific rewrite. Compare proposals,
compliance verdicts, follow-up actions, and supervisor reports with your
GPT-4o demo runs before presenting the model switch as equivalent quality.

---

## 1. Architecture

```
config.py                     <- single place to set LLM_PROVIDER (anthropic|openai|mock)

llm/                           LLM abstraction layer (provider-agnostic)
  base.py                      Common LLMResponse / ToolCall / LLMClient interface
  anthropic_client.py          Claude backend (real API)
  openai_client.py             GPT backend (real API)
  mock_client.py                Deterministic offline backend (no API key needed)
  factory.py                    get_llm_client() - the one switch every agent uses

core/                           Generic multi-agent building blocks
  tool.py                       Tool spec (translates to Anthropic/OpenAI function schemas)
  agent.py                      Agent (single-shot JSON reasoning) + ToolAgent (tool-calling loop)
  utils.py                      Lenient JSON extraction from LLM text

genesys/
  data.py                        Genesys Cloud interactions, Architect flow
                                  definitions, and follow-up candidate interactions

crm/                            Sample CRM & ticketing app (Use Case 2's "other application")
  store.py                      Data layer (JSON-file backed) + backend-team
  app.py                        Standalone FastAPI app (its own service, own port)
  client.py                     HTTP client used by agents as Tool handlers
  seed.py                       Sample customers

usecase1_cx_optimization/       Detect -> Diagnose -> Fix -> Simulate -> Approve -> Deploy -> Measure
  agents.py                      SignalMiningSwarm, RootCauseAgent, FixAgent,
                                  AdversarialSimulationSwarm, ComplianceAgent, MeasurementAgent
  orchestrator.py                Pipeline + human-in-the-loop supervisor gate
  run_demo.py

usecase2_customer_followup/      Case intake + persistent per-case follow-up agent
  agents.py                      CaseIntakeAgent, FollowUpOwnerAgent (both real tool-calling agents)
  orchestrator.py                Intake -> N simulated days -> final case/communications summary
  run_demo.py

usecase3_autonomous_supervisor/  Ask Your Contact Center
  agents.py                      Planner -> tool-using analyst -> reporter
  run_demo.py

main.py                          CLI: python main.py 1|2|3|all
```

### Why this is "multi-agent"

Every stage of every use case is its own agent with its own system prompt and
its own narrow job - they never share a single "do everything" prompt:

- **Use Case 1** runs a literal *swarm*: a `SignalMiningSwarm` spins up one
  specialist agent per (flow, issue) cluster **in parallel** (via
  `ThreadPoolExecutor`), followed by dedicated `RootCauseAgent`, `FixAgent`,
  a 4-persona `AdversarialSimulationSwarm` (also parallel), a `ComplianceAgent`,
  and a `MeasurementAgent` - chained together by an orchestrator, with a human
  approval gate before anything is "deployed."
- **Use Case 2** uses genuine LLM **tool-calling** agents (`ToolAgent`): a
  `CaseIntakeAgent` decides whether to open a case and calls `create_case`; a
  persistent `FollowUpOwnerAgent` checks in on each open case every simulated
  "day" and calls real tools (`get_case`, `create_ticket`, `get_ticket_status`,
  `escalate_ticket`, `send_customer_update`, `close_case`) against the sample
  CRM's REST API - the same shape of interaction it would have with a real
  CRM/ticketing system.
- **Use Case 3** is a planner agent -> tool-using analyst agent -> reporter
  agent pipeline that answers arbitrary supervisor questions.

### The LLM switch

Every agent is built from `get_llm_client()`. Change one line in `.env`:

```
LLM_PROVIDER=anthropic   # Claude
LLM_PROVIDER=openai      # GPT
LLM_PROVIDER=mock        # offline, deterministic, no API key needed
```

and every agent across all three use cases uses the new backend - no other
code changes required. This works because `llm/base.py` defines a single
provider-agnostic message/tool-call shape, and each client (`AnthropicClient`,
`OpenAIClient`) just translates to/from it.

---

## 2. Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set LLM_PROVIDER and the matching API key, or leave LLM_PROVIDER=mock
```

You do **not** need any API key to run the full demo end to end (`LLM_PROVIDER=mock`
is the default in `.env.example`).

To use a real model:
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5      # adjust to whatever Claude model you have access to
```
or
```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-6-luna             # or another GPT model available to your project
```

---

## 3. Running the demos

```bash
python main.py 1      # Use Case 1: Autonomous CX Optimization
python main.py 2       # Use Case 2: Autonomous Customer Follow-Up (auto-starts the sample CRM)
python main.py 3        # Use Case 3: Autonomous Supervisor
python main.py all       # all three in sequence
```

Or run each module directly, e.g. `python -m usecase1_cx_optimization.run_demo`.

