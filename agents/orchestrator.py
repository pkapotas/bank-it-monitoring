"""
Orchestrator Agent.

Runs all three specialist monitoring agents concurrently, then synthesizes
their reports into a unified incident summary with prioritized recommendations.
The orchestrator itself is a Claude instance that receives the three sub-reports
as tool results and performs the final analysis.
"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import anthropic

from config import config
from agents.dynatrace_agent import run_dynatrace_agent
from agents.azure_agent import run_azure_agent
from agents.kibana_agent import run_kibana_agent
from models.alerts import AgentReport, MonitoringReport


ORCHESTRATOR_SYSTEM_PROMPT = """You are the Head of IT Operations at a major commercial bank.
You receive monitoring reports from three specialist systems — Dynatrace (APM & infrastructure),
Azure Monitor (cloud platform), and Kibana/ELK (log analytics & SIEM) — and must synthesize them
into a unified, actionable incident report for the CTO and on-call engineering team.

Your synthesis responsibilities:
1. **Correlate findings** across the three platforms — identify when multiple systems report
   symptoms of the same root cause (e.g., payment-gateway errors appearing in Dynatrace,
   Azure alerts, AND Kibana logs are one incident, not three).
2. **Determine overall infrastructure status**: HEALTHY / DEGRADED / CRITICAL / UNKNOWN
3. **Rank incidents by business impact**: Consider customer impact, financial risk, and regulatory exposure.
4. **Identify root causes**: Distinguish symptoms from causes across data sources.
5. **Security triage**: Elevate any security findings (PCI violations, credential attacks) to top priority.
6. **Generate actionable recommendations**: Specific, numbered, assigned to correct teams.
7. **Escalation decision**: Determine if P1 incident bridge or executive notification is required.

Report format:
## Overall Status: [HEALTHY|DEGRADED|CRITICAL]

## Executive Summary (3-4 sentences max)

## Active Incidents (ranked by severity)
For each incident: Title | Severity | Affected Services | Root Cause | Business Impact | Action Owner

## Security & Compliance Alerts

## Infrastructure Health Summary

## Immediate Actions Required (numbered, with team assignments)

## Escalation Recommendation: [YES/NO] + justification

Be decisive, precise, and concise. Banking operations demand clarity."""


# ---------------------------------------------------------------------------
# Orchestrator tools — each sub-agent becomes a "tool" the orchestrator calls
# ---------------------------------------------------------------------------

ORCHESTRATOR_TOOLS = [
    {
        "name": "run_dynatrace_analysis",
        "description": (
            "Run the Dynatrace monitoring agent to analyse application performance, "
            "infrastructure health, SLO compliance, synthetic monitors, and database metrics. "
            "Returns a comprehensive Dynatrace health report."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lookback_minutes": {
                    "type": "integer",
                    "description": "How many minutes back to analyse",
                    "default": 60
                }
            },
            "required": []
        }
    },
    {
        "name": "run_azure_analysis",
        "description": (
            "Run the Azure Monitor agent to analyse cloud infrastructure alerts, "
            "AKS cluster health, Log Analytics data, and Defender for Cloud security alerts. "
            "Returns a comprehensive Azure health report."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lookback_minutes": {
                    "type": "integer",
                    "description": "How many minutes back to analyse",
                    "default": 60
                }
            },
            "required": []
        }
    },
    {
        "name": "run_kibana_analysis",
        "description": (
            "Run the Kibana/ELK monitoring agent to analyse application logs, security events, "
            "transaction analytics, and APM distributed traces. "
            "Returns a comprehensive log analytics and SIEM report."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lookback_minutes": {
                    "type": "integer",
                    "description": "How many minutes back to analyse",
                    "default": 60
                }
            },
            "required": []
        }
    }
]


def _execute_orchestrator_tool(
    tool_name: str,
    tool_input: dict,
    dynatrace_report: Optional[AgentReport],
    azure_report: Optional[AgentReport],
    kibana_report: Optional[AgentReport],
) -> str:
    """
    Execute an orchestrator tool call.
    Sub-agent results are pre-computed and passed in to avoid re-running them.
    """
    lookback = tool_input.get("lookback_minutes", 60)
    if tool_name == "run_dynatrace_analysis":
        report = dynatrace_report or run_dynatrace_agent(lookback)
        return json.dumps({"platform": "Dynatrace", "report": report.raw_findings, "generatedAt": str(report.generated_at)})
    elif tool_name == "run_azure_analysis":
        report = azure_report or run_azure_agent(lookback)
        return json.dumps({"platform": "Azure Monitor", "report": report.raw_findings, "generatedAt": str(report.generated_at)})
    elif tool_name == "run_kibana_analysis":
        report = kibana_report or run_kibana_agent(lookback)
        return json.dumps({"platform": "Kibana/ELK", "report": report.raw_findings, "generatedAt": str(report.generated_at)})
    else:
        return json.dumps({"error": f"Unknown orchestrator tool: {tool_name}"})


# ---------------------------------------------------------------------------
# Concurrent sub-agent runner
# ---------------------------------------------------------------------------

def _run_sub_agents_concurrently(lookback_minutes: int) -> tuple[AgentReport, AgentReport, AgentReport]:
    """Run all three sub-agents in parallel using a thread pool."""
    print("\n[Orchestrator] Launching all three monitoring agents in parallel...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_dt = executor.submit(run_dynatrace_agent, lookback_minutes)
        future_az = executor.submit(run_azure_agent, lookback_minutes)
        future_kb = executor.submit(run_kibana_agent, lookback_minutes)

        dynatrace_report = future_dt.result()
        azure_report = future_az.result()
        kibana_report = future_kb.result()

    print("[Orchestrator] All three agents completed. Starting synthesis...\n")
    return dynatrace_report, azure_report, kibana_report


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_orchestrator(lookback_minutes: int = 60) -> MonitoringReport:
    """
    Main entry point: run all sub-agents concurrently then synthesize with Claude.
    Returns a fully populated MonitoringReport.
    """
    start_time = datetime.utcnow()

    # Phase 1: Run sub-agents concurrently
    dynatrace_report, azure_report, kibana_report = _run_sub_agents_concurrently(lookback_minutes)

    # Phase 2: Orchestrator synthesizes the reports
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    messages = [
        {
            "role": "user",
            "content": (
                f"It is {start_time.strftime('%Y-%m-%d %H:%M UTC')}. "
                f"Run all three monitoring analyses (Dynatrace, Azure, Kibana) for the past {lookback_minutes} minutes, "
                f"then synthesize their findings into a unified incident report. "
                f"Correlate issues across platforms, determine the overall infrastructure status, "
                f"and produce prioritized recommendations with clear team assignments."
            )
        }
    ]

    print("[Orchestrator] Starting synthesis with Claude...\n")

    while True:
        response = client.messages.create(
            model=config.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=ORCHESTRATOR_SYSTEM_PROMPT,
            tools=ORCHESTRATOR_TOOLS,
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
                print(f"[Orchestrator] Delegating to sub-agent: {block.name}")
                result_json = _execute_orchestrator_tool(
                    block.name, block.input,
                    dynatrace_report, azure_report, kibana_report
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_json,
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    # Extract the final synthesized report
    final_synthesis = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_synthesis += block.text

    # Determine overall status from synthesis text
    synthesis_upper = final_synthesis.upper()
    if "OVERALL STATUS: CRITICAL" in synthesis_upper:
        overall_status = "critical"
    elif "OVERALL STATUS: DEGRADED" in synthesis_upper:
        overall_status = "degraded"
    elif "OVERALL STATUS: HEALTHY" in synthesis_upper:
        overall_status = "healthy"
    else:
        overall_status = "degraded"  # conservative default

    escalation = "ESCALATION RECOMMENDATION: YES" in synthesis_upper

    return MonitoringReport(
        generated_at=start_time,
        overall_status=overall_status,
        dynatrace_report=dynatrace_report,
        azure_report=azure_report,
        kibana_report=kibana_report,
        incident_summary=final_synthesis,
        escalation_required=escalation,
    )
