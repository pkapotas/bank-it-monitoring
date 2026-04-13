"""
Orchestrator Agent — v2.

Runs all 7 specialist agents concurrently, enriches with analytics context
(baselines, correlation, memory), and synthesizes into a unified incident report
with per-agent confidence scores.

Agents:
  1. DynatraceAgent   -- APM, infrastructure, SLOs
  2. AzureAgent       -- Cloud platform, AKS, security
  3. KibanaAgent      -- Log analytics, SIEM, APM traces
  4. AuditAgent       -- Privileged access, compliance violations
  5. ComplianceAgent  -- PCI-DSS scorecard
  6. CostAgent        -- Azure spend anomalies
  [PostMortemAgent runs on-demand for resolved incidents]
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import anthropic

from config import config
from agents.dynatrace_agent  import run_dynatrace_agent
from agents.azure_agent      import run_azure_agent
from agents.kibana_agent     import run_kibana_agent
from agents.audit_agent      import run_audit_agent
from agents.compliance_agent import run_compliance_agent
from agents.cost_agent       import run_cost_agent
from models.alerts           import AgentReport, MonitoringReport
from analytics.baselines     import get_mock_anomaly_report
from analytics.correlation   import get_mock_correlation_report
from memory.store            import get_mock_memory_context


ORCHESTRATOR_SYSTEM_PROMPT = """You are the Head of IT Operations at a major commercial bank.
You receive monitoring reports from 6 specialist systems and must synthesize them into a unified,
actionable incident report for the CTO and on-call engineering team.

Your synthesis responsibilities:
1. CORRELATE findings across platforms -- same root cause appearing in multiple systems = one incident.
2. Determine OVERALL STATUS: HEALTHY / DEGRADED / CRITICAL / UNKNOWN.
3. RANK incidents by business impact: customer impact, financial risk, regulatory exposure.
4. SECURITY TRIAGE: PCI violations and active attacks always rank #1 and #2.
5. LINK cost anomalies to operational incidents (runaway auto-scale = operational + cost incident).
6. Use MEMORY CONTEXT to identify recurring patterns and reference past resolutions.
7. Assign CONFIDENCE SCORE (0.0-1.0) to each finding based on data quality and consistency.
8. Generate IMMEDIATE ACTIONS: specific, numbered, assigned to correct teams with urgency.
9. ESCALATION DECISION: Is a P1 incident bridge or executive notification required?

Report format:
## Overall Status: [HEALTHY|DEGRADED|CRITICAL]
## Confidence Score: [0.0-1.0] -- overall confidence in this assessment
## Executive Summary (3-4 sentences)
## Active Incidents (ranked, each with: Title | Severity | Confidence | Root Cause | Impact | Owner)
## Security & Compliance Alerts
## Cost Impact (link operational issues to EUR waste)
## Memory Context (similar past incidents and their resolutions)
## Immediate Actions (numbered, team assigned, urgency: NOW/15min/30min/1hr)
## Escalation: [YES/NO] + justification

Be decisive, precise, and concise. Banking operations demand clarity."""


ORCHESTRATOR_TOOLS = [
    {
        "name": "run_dynatrace_analysis",
        "description": "Run the Dynatrace agent (APM, infrastructure, SLOs, synthetics, databases).",
        "input_schema": {"type": "object", "properties": {"lookback_minutes": {"type": "integer", "default": 60}}, "required": []},
    },
    {
        "name": "run_azure_analysis",
        "description": "Run the Azure Monitor agent (cloud alerts, AKS, Log Analytics, Defender).",
        "input_schema": {"type": "object", "properties": {"lookback_minutes": {"type": "integer", "default": 60}}, "required": []},
    },
    {
        "name": "run_kibana_analysis",
        "description": "Run the Kibana/ELK agent (log analysis, SIEM, APM traces, alert rules).",
        "input_schema": {"type": "object", "properties": {"lookback_minutes": {"type": "integer", "default": 60}}, "required": []},
    },
    {
        "name": "run_audit_analysis",
        "description": "Run the Audit agent (privileged access, compliance violations, config changes).",
        "input_schema": {"type": "object", "properties": {"lookback_hours": {"type": "integer", "default": 24}}, "required": []},
    },
    {
        "name": "run_compliance_analysis",
        "description": "Run the Compliance agent (PCI-DSS scorecard across all 12 requirements).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_cost_analysis",
        "description": "Run the Cost agent (Azure spend anomalies, budget forecast, optimization).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _run_all_agents_concurrently(lookback_minutes: int) -> dict[str, AgentReport]:
    """Run all 6 specialist agents in parallel. Return dict keyed by agent name."""
    print("\n[Orchestrator] Launching all 6 monitoring agents in parallel...")
    futures = {}
    results = {}

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures["dynatrace"]  = executor.submit(run_dynatrace_agent,  lookback_minutes)
        futures["azure"]      = executor.submit(run_azure_agent,      lookback_minutes)
        futures["kibana"]     = executor.submit(run_kibana_agent,      lookback_minutes)
        futures["audit"]      = executor.submit(run_audit_agent,       24)
        futures["compliance"] = executor.submit(run_compliance_agent)
        futures["cost"]       = executor.submit(run_cost_agent)

        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as e:
                print(f"  [Orchestrator] {name} agent failed: {e}")
                results[name] = AgentReport(
                    agent_name=f"{name}Agent",
                    platform=name,
                    generated_at=datetime.utcnow(),
                    error=str(e),
                )

    print("[Orchestrator] All 6 agents completed.\n")
    return results


def _execute_orchestrator_tool(tool_name: str, tool_input: dict, reports: dict) -> str:
    """Map orchestrator tool calls to pre-computed agent reports."""
    mapping = {
        "run_dynatrace_analysis":  "dynatrace",
        "run_azure_analysis":      "azure",
        "run_kibana_analysis":     "kibana",
        "run_audit_analysis":      "audit",
        "run_compliance_analysis": "compliance",
        "run_cost_analysis":       "cost",
    }
    key = mapping.get(tool_name)
    if not key:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    report = reports.get(key)
    if not report:
        return json.dumps({"error": f"No report for {key}"})

    return json.dumps({
        "platform":    report.platform,
        "report":      report.raw_findings or report.error or "No findings",
        "generatedAt": str(report.generated_at),
        "hasError":    bool(report.error),
    })


def _compute_confidence_score(reports: dict) -> float:
    """
    Compute overall confidence score based on how many agents succeeded
    and whether findings are consistent across platforms.
    """
    total = len(reports)
    successful = sum(1 for r in reports.values() if not r.error)
    base_confidence = successful / total if total > 0 else 0.0

    # Boost if multiple platforms agree on the same service
    # (simplified: check if payment-gateway appears in most reports)
    agreement_boost = 0.0
    keyword = "payment-gateway"
    agreeing = sum(1 for r in reports.values() if r.raw_findings and keyword in r.raw_findings)
    if agreeing >= 3:
        agreement_boost = 0.05

    return round(min(1.0, base_confidence + agreement_boost), 2)


def run_orchestrator(lookback_minutes: int = 60) -> MonitoringReport:
    """
    Main entry point. Run all 6 agents concurrently, enrich with analytics,
    then synthesize with Claude into a unified MonitoringReport.
    """
    start_time = datetime.utcnow()

    # Phase 1: Run all agents concurrently
    reports = _run_all_agents_concurrently(lookback_minutes)

    # Phase 2: Gather analytics context
    anomaly_ctx    = get_mock_anomaly_report()
    correlation_ctx = get_mock_correlation_report()
    memory_ctx     = get_mock_memory_context()
    confidence     = _compute_confidence_score(reports)

    # Phase 3: Orchestrator synthesis
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    analytics_summary = (
        f"\n\n--- ANALYTICS CONTEXT ---\n"
        f"Anomaly Detection: {anomaly_ctx['total_anomalies']} anomalies detected "
        f"({anomaly_ctx['by_severity']['critical']} critical, z-score threshold 2.5).\n"
        f"Alert Correlation: {correlation_ctx['total_clusters']} incident clusters from {correlation_ctx['total_alerts']} alerts. "
        f"Key cluster: {correlation_ctx['clusters'][0]['root_title'] if correlation_ctx['clusters'] else 'none'}.\n"
        f"Memory Context: {memory_ctx['total_incidents_in_memory']} past incidents. "
        f"Top similar: {memory_ctx['similar_incidents'][0]['summary_text'][:120] if memory_ctx['similar_incidents'] else 'none'}...\n"
        f"Agent Confidence: {confidence:.0%} ({sum(1 for r in reports.values() if not r.error)}/6 agents succeeded).\n"
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"It is {start_time.strftime('%Y-%m-%d %H:%M UTC')}. "
                f"Run all 6 monitoring analyses (Dynatrace, Azure, Kibana, Audit, Compliance, Cost) "
                f"for the past {lookback_minutes} minutes, then synthesize their findings. "
                f"Cross-correlate issues across platforms, determine overall status, "
                f"and produce prioritized recommendations. "
                f"{analytics_summary}"
            ),
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
                print(f"[Orchestrator] Delegating to: {block.name}")
                result_json = _execute_orchestrator_tool(block.name, block.input, reports)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_json})

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    final_synthesis = "".join(block.text for block in response.content if hasattr(block, "text"))

    # Extract status and escalation
    synth_upper = final_synthesis.upper()
    if "OVERALL STATUS: CRITICAL" in synth_upper:
        overall_status = "critical"
    elif "OVERALL STATUS: DEGRADED" in synth_upper:
        overall_status = "degraded"
    elif "OVERALL STATUS: HEALTHY" in synth_upper:
        overall_status = "healthy"
    else:
        overall_status = "degraded"

    escalation = "ESCALATION: YES" in synth_upper or "ESCALATION RECOMMENDATION: YES" in synth_upper

    return MonitoringReport(
        generated_at=start_time,
        overall_status=overall_status,
        dynatrace_report=reports.get("dynatrace"),
        azure_report=reports.get("azure"),
        kibana_report=reports.get("kibana"),
        incident_summary=final_synthesis,
        escalation_required=escalation,
    )
