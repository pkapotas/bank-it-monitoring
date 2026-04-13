"""
Dynatrace Monitoring Agent.

A Claude-powered agent that uses Dynatrace tools to assess the health of
banking applications and infrastructure, then produces a structured report.
"""
import json
from datetime import datetime

import anthropic

from config import config
from tools.dynatrace_tools import DYNATRACE_TOOLS, execute_dynatrace_tool
from models.alerts import AgentReport


DYNATRACE_SYSTEM_PROMPT = """You are a senior Dynatrace monitoring engineer at a major commercial bank.
Your job is to perform a comprehensive health check of banking IT services and infrastructure using
the Dynatrace tools available to you.

Banking services you must always check:
- payment-gateway (CRITICAL: processes all customer payments)
- core-banking-api (CRITICAL: account balances and transactions)
- fraud-detection (HIGH: real-time ML fraud scoring)
- authentication-service (HIGH: customer and employee login)
- transaction-processor (HIGH: transaction lifecycle management)
- swift-connector (HIGH: interbank SWIFT messaging)
- atm-network (MEDIUM: ATM availability)

Your investigation strategy:
1. Start with active problems (dynatrace_get_problems) for immediate awareness
2. Check SLO compliance (dynatrace_get_slo_status) for regulatory impact
3. Get metrics for any service showing issues
4. Check synthetic monitors to understand customer-facing impact
5. Review database metrics if application issues are detected
6. Check infrastructure health for resource bottlenecks

Produce a concise but complete report covering:
- CRITICAL/HIGH severity findings with business impact
- Services currently in violation of SLAs
- Root causes identified
- Recommended immediate actions (numbered list)
- Services that are healthy (brief confirmation)

Be specific: include metric values, percentages, and names. Avoid vague statements."""


def run_dynatrace_agent(lookback_minutes: int = 60) -> AgentReport:
    """
    Run the Dynatrace monitoring agent and return an AgentReport.
    Uses the manual agentic loop for full control over tool execution.
    """
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    messages = [
        {
            "role": "user",
            "content": (
                f"Perform a comprehensive Dynatrace health check for the past {lookback_minutes} minutes. "
                f"Focus on banking service health, active problems, SLO compliance, and infrastructure status. "
                f"Use your tools systematically and provide a detailed report with prioritized findings."
            )
        }
    ]

    print(f"  [Dynatrace Agent] Starting investigation (last {lookback_minutes}m)...")

    while True:
        response = client.messages.create(
            model=config.model,
            max_tokens=8096,
            thinking={"type": "adaptive"},
            system=DYNATRACE_SYSTEM_PROMPT,
            tools=DYNATRACE_TOOLS,
            messages=messages,
        )

        # Append assistant response to history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason != "tool_use":
            break

        # Execute all tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [Dynatrace Agent] Calling tool: {block.name}({json.dumps(block.input, default=str)[:80]}...)")
                result_json = execute_dynatrace_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_json,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    # Extract the final text report
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text

    print(f"  [Dynatrace Agent] Investigation complete.")
    return AgentReport(
        agent_name="DynatraceAgent",
        platform="Dynatrace",
        generated_at=datetime.utcnow(),
        raw_findings=final_text,
    )
