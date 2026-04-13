"""
Azure Monitoring Agent.

A Claude-powered agent that uses Azure Monitor tools to assess the health of
Azure-hosted banking infrastructure and services.
"""
import json
from datetime import datetime

import anthropic

from config import config
from tools.azure_tools import AZURE_TOOLS, execute_azure_tool
from models.alerts import AgentReport


AZURE_SYSTEM_PROMPT = """You are a senior Azure cloud operations engineer at a major commercial bank.
Your role is to monitor and assess the health of the bank's Azure infrastructure using
Azure Monitor, Log Analytics, Defender for Cloud, and AKS monitoring tools.

Azure resources critical to banking operations:
- AKS clusters: payment-gateway-aks, core-banking-aks (Kubernetes workloads)
- Azure SQL: core-banking-sqlserver (primary transactional database)
- Service Bus: bank-servicebus (event-driven messaging for transactions)
- API Management: bank-apim (API gateway for all external and partner APIs)
- Azure AD: authentication and authorization
- Key Vault, Storage Accounts, and Virtual Networks

Your investigation strategy:
1. Check active Azure Monitor alerts first (azure_get_active_alerts)
2. Check Azure Service Health for platform-level incidents
3. Review AKS cluster health for Kubernetes workloads
4. Query Log Analytics for recent errors and anomalies (azure_query_logs)
5. Get metrics for any resources flagged with issues (azure_get_resource_metrics)
6. Check Defender for Cloud security alerts (azure_get_security_alerts)

Produce a clear report covering:
- Platform-level Azure incidents affecting the bank
- Infrastructure alerts and their business impact
- AKS cluster health (nodes, pods, deployments)
- Security threats detected by Defender for Cloud
- Recommended immediate actions (numbered list)
- Healthy resources (brief confirmation)

Prioritize: customer-impacting issues > security threats > infrastructure degradation > warnings."""


def run_azure_agent(lookback_minutes: int = 60) -> AgentReport:
    """
    Run the Azure monitoring agent and return an AgentReport.
    """
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    messages = [
        {
            "role": "user",
            "content": (
                f"Perform a comprehensive Azure infrastructure health check for the past {lookback_minutes} minutes. "
                f"Check active alerts, AKS cluster health, Log Analytics for errors, "
                f"Azure service health, and security alerts from Defender for Cloud. "
                f"Provide a prioritized report with business impact and recommended actions."
            )
        }
    ]

    print(f"  [Azure Agent] Starting investigation (last {lookback_minutes}m)...")

    while True:
        response = client.messages.create(
            model=config.model,
            max_tokens=8096,
            thinking={"type": "adaptive"},
            system=AZURE_SYSTEM_PROMPT,
            tools=AZURE_TOOLS,
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
                print(f"  [Azure Agent] Calling tool: {block.name}({json.dumps(block.input, default=str)[:80]}...)")
                result_json = execute_azure_tool(block.name, block.input)
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

    print(f"  [Azure Agent] Investigation complete.")
    return AgentReport(
        agent_name="AzureAgent",
        platform="Azure Monitor",
        generated_at=datetime.utcnow(),
        raw_findings=final_text,
    )
