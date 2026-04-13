"""
Kibana / ELK Stack Monitoring Agent.

A Claude-powered agent that uses Kibana and Elasticsearch tools to analyse
application logs, security events, transaction analytics, and APM traces
for the bank's IT operations.
"""
import json
from datetime import datetime

import anthropic

from config import config
from tools.kibana_tools import KIBANA_TOOLS, execute_kibana_tool
from models.alerts import AgentReport


KIBANA_SYSTEM_PROMPT = """You are a senior log analytics and SIEM engineer at a major commercial bank.
Your responsibility is to analyse application logs, security events, transaction data,
and distributed traces using Kibana and Elasticsearch to identify issues, threats, and anomalies.

Banking log sources you monitor:
- Application logs: all microservices (payment-gateway, core-banking-api, etc.)
- Security/SIEM: authentication logs, access logs, privilege usage
- Transaction logs: payment events, SWIFT messages, ATM activity
- APM traces: distributed transaction tracing for slow/failed requests
- Audit logs: PCI-DSS and regulatory compliance events

Your investigation strategy:
1. Check error rate aggregation across all services to find hotspots
2. Search logs for critical errors in top-offending services
3. Check security events (credential stuffing, PCI violations, anomalous access)
4. Analyse transaction analytics for volume and failure rate anomalies
5. Get APM traces for slow or failing critical transactions
6. Review Kibana alert rules for any muted or failed rules (coverage gaps)

Produce a report covering:
- Log analysis findings: services with elevated error rates and root causes
- Security events: threats, compliance violations, suspicious patterns
- Transaction health: failure rates, anomalies, high-value transaction issues
- APM insights: slow transactions and identified bottlenecks
- Compliance flags: any PCI-DSS, GDPR, or regulatory violations in logs
- Recommended immediate actions (numbered list)

Be precise: include log message excerpts, counts, and timestamps where relevant."""


def run_kibana_agent(lookback_minutes: int = 60) -> AgentReport:
    """
    Run the Kibana monitoring agent and return an AgentReport.
    """
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    messages = [
        {
            "role": "user",
            "content": (
                f"Perform a comprehensive log and security analysis for the past {lookback_minutes} minutes. "
                f"Check error rates, search logs for critical issues, review security events "
                f"(especially authentication failures and PCI violations), analyse transaction health, "
                f"and review APM traces for slow transactions. Provide a detailed report with prioritized findings."
            )
        }
    ]

    print(f"  [Kibana Agent] Starting investigation (last {lookback_minutes}m)...")

    while True:
        response = client.messages.create(
            model=config.model,
            max_tokens=8096,
            thinking={"type": "adaptive"},
            system=KIBANA_SYSTEM_PROMPT,
            tools=KIBANA_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [Kibana Agent] Calling tool: {block.name}({json.dumps(block.input, default=str)[:80]}...)")
                result_json = execute_kibana_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_json,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text

    print(f"  [Kibana Agent] Investigation complete.")
    return AgentReport(
        agent_name="KibanaAgent",
        platform="Kibana/ELK",
        generated_at=datetime.utcnow(),
        raw_findings=final_text,
    )
