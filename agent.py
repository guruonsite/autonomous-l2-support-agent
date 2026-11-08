import json
import os
import logging
from typing import Any, Dict, List
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("L2SupportAgent")

# Works with OpenAI, OpenRouter, or local Ollama (e.g., base_url="http://localhost:11434/v1")
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "your-api-key-here"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://openai.com")
)
MODEL_NAME = os.getenv("AGENT_MODEL", "gpt-4o-mini")


# --- 1. DIAGNOSTIC TOOLS (Simulating Real L2 API & Log Checks) ---

def check_endpoint_health(endpoint: str) -> str:
    """Checks live HTTP status and latency for an API endpoint."""
    logger.info(f"TOOL EXEC -> check_endpoint_health(endpoint='{endpoint}')")
    mock_status = {
        "/v2/webhooks/dispatch": {"status_code": 200, "latency_ms": 48, "healthy": True},
        "/v2/data/ingest": {"status_code": 429, "latency_ms": 812, "healthy": False, "note": "Upstream rate limit threshold exceeded"}
    }
    result = mock_status.get(endpoint, {"status_code": 404, "healthy": False, "note": "Unknown endpoint"})
    return json.dumps(result)


def inspect_recent_logs(tenant_id: str) -> str:
    """Fetches recent structured JSON error logs for a specific client tenant."""
    logger.info(f"TOOL EXEC -> inspect_recent_logs(tenant_id='{tenant_id}')")
    mock_logs = {
        "org_8841": [
            {"ts": "2026-11-08T12:10:02Z", "endpoint": "/v2/data/ingest", "http_status": 429, "retry_after_sec": 30, "payload_size_kb": 1420},
            {"ts": "2026-11-08T12:10:04Z", "endpoint": "/v2/data/ingest", "http_status": 429, "retry_after_sec": 30, "payload_size_kb": 1435},
            {"ts": "2026-11-08T12:10:05Z", "endpoint": "/v2/webhooks/dispatch", "http_status": 200, "latency_ms": 51}
        ]
    }
    logs = mock_logs.get(tenant_id, [])
    return json.dumps({"tenant_id": tenant_id, "recent_errors": logs})


def search_runbook(error_code: str) -> str:
    """Queries internal L2 engineering runbooks for known remediation steps."""
    logger.info(f"TOOL EXEC -> search_runbook(error_code='{error_code}')")
    runbooks = {
        "429": (
            "RUNBOOK-429: Burst payloads >1MB on /v2/data/ingest trigger per-tenant rate throttling (60 req/min). "
            "Remediation: Advise client to batch payloads under 500KB and implement exponential backoff respecting 'retry_after_sec'. "
            "No backend hotfix required unless 5xx errors persist."
        ),
        "401": "RUNBOOK-401: Verify bearer token rotation timestamp and check clock skew > 30s."
    }
    return runbooks.get(str(error_code), "No matching runbook found. Escalate to Tier-3 Platform Engineering.")


# --- 2. TOOL SCHEMA DEFINITIONS FOR THE LLM ---

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_endpoint_health",
            "description": "Check live HTTP status code and latency for a given API endpoint path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "endpoint": {"type": "string", "description": "API path, e.g. /v2/data/ingest"}
                },
                "required": ["endpoint"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_recent_logs",
            "description": "Retrieve recent API error logs for a given tenant_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tenant_id": {"type": "string", "description": "Client organization ID, e.g. org_8841"}
                },
                "required": ["tenant_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_runbook",
            "description": "Look up internal L2 remediation procedures by HTTP status or error code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "error_code": {"type": "string", "description": "HTTP error code string, e.g. 429"}
                },
                "required": ["error_code"]
            }
        }
    }
]

TOOL_DISPATCH = {
    "check_endpoint_health": check_endpoint_health,
    "inspect_recent_logs": inspect_recent_logs,
    "search_runbook": search_runbook
}


# --- 3. AUTONOMOUS AGENT DECISION LOOP ---

def run_triage_agent(ticket_payload: str, max_steps: int = 5) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are an autonomous L2 Platform Support Engineer agent. "
                "Investigate incoming support tickets by calling diagnostic tools to inspect logs, verify endpoint health, "
                "and consult internal runbooks. Never guess root causes without tool verification. "
                "Once verified, output a concise Root Cause Analysis (RCA) with concrete next steps."
            )
        },
        {"role": "user", "content": ticket_payload}
    ]

    for step in range(1, max_steps + 1):
        logger.info(f"--- Agent Reasoning Step {step}/{max_steps} ---")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1
        )
        msg = response.choices[0].message
        messages.append(msg)

        # If no tool calls remain, the agent has reached a verified conclusion
        if not msg.tool_calls:
            logger.info("Investigation complete. Generating final RCA.")
            return msg.content or "No resolution generated."

        # Execute each tool requested by the model and feed outputs back into context
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            handler = TOOL_DISPATCH.get(fn_name)

            tool_output = handler(**fn_args) if handler else json.dumps({"error": f"Unknown tool {fn_name}"})
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_output
            })

    return "Max reasoning steps reached without full resolution. Escalating ticket to Tier-3 Engineering."


if __name__ == "__main__":
    sample_ticket = (
        "TICKET #4092 | Tenant: org_8841 | Priority: High\n"
        "Summary: Automated data sync pipeline failing intermittently over the last 15 minutes. "
        "Webhooks appear fine, but batch ingestion jobs are dropping."
    )
    print("\n=== INCOMING TICKET ===")
    print(sample_ticket)
    print("\n=== RUNNING AUTONOMOUS TRIAGE ===")
    final_rca = run_triage_agent(sample_ticket)
    print("\n=== FINAL VERIFIED RCA ===")
    print(final_rca)
