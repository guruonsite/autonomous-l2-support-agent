# autonomous-l2-support-agent
(Python)—the exact project that checks the "building AI agents to automate workflows" box for L2 Support and Platform Engineering roles.


# Autonomous L2 Support Triage Agent

A lightweight, framework-free Python agent designed to automate Tier-2 API and platform support investigations using native LLM tool-calling loops.

## Architecture

```text
[Incoming Support Ticket]
          │
          ▼
┌───────────────────┐     Tool Calls      ┌──────────────────────────┐
│  LLM Decision     │ ──────────────────► │  Diagnostic Tool Belt    │
│  Loop (max 5)     │ ◄────────────────── │  • inspect_recent_logs   │
└───────────────────┘     JSON Outputs    │  • check_endpoint_health │
          │                               │  • search_runbook        │
          ▼                               └──────────────────────────┘
[Verified Root Cause Analysis & Escalation Decision]
```

## Key Engineering Features
* **Zero Heavy Abstractions:** Built directly on standard Python and OpenAI-compatible function-calling schemas (`openai` SDK) for predictable state management and easy debugging.
* **Bounded Execution Guardrails:** Enforces a strict `max_steps` loop ceiling to prevent runaway API token usage or infinite tool-call cycles.
* **Evidence-First Triage:** System instructions require log and endpoint verification before generating a Root Cause Analysis (RCA) or Tier-3 escalation summary.

## Quickstart
```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
python agent.py
```

## Sample Execution Trace
```text
12:15:01 [INFO] --- Agent Reasoning Step 1/5 ---
12:15:02 [INFO] TOOL EXEC -> inspect_recent_logs(tenant_id='org_8841')
12:15:02 [INFO] TOOL EXEC -> check_endpoint_health(endpoint='/v2/data/ingest')
12:15:03 [INFO] --- Agent Reasoning Step 2/5 ---
12:15:04 [INFO] TOOL EXEC -> search_runbook(error_code='429')
12:15:05 [INFO] --- Agent Reasoning Step 3/5 ---
12:15:06 [INFO] Investigation complete. Generating final RCA.
```
