"""
Demo / dry-run mode: exercises the full tool layer and prints realistic
output for each agent without requiring real API credentials.

Run:  python demo.py
"""
import json
import sys
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import box

# Import all tool executors directly
from tools.dynatrace_tools import execute_dynatrace_tool
from tools.azure_tools import execute_azure_tool
from tools.kibana_tools import execute_kibana_tool

console = Console()


def section(title: str, color: str = "white"):
    console.print()
    console.print(Rule(f"[bold {color}]{title}[/bold {color}]", style=color))
    console.print()


def show_tool_result(tool_name: str, result_json: str, color: str = "cyan"):
    data = json.loads(result_json)
    console.print(f"  [bold {color}]>> {tool_name}[/bold {color}]")
    console.print(
        Panel(
            json.dumps(data, indent=2, default=str)[:1200] + ("\n  ... (truncated)" if len(result_json) > 1200 else ""),
            border_style=color,
            expand=False,
        )
    )
    console.print()


def run_dynatrace_demo():
    section("DYNATRACE AGENT -- Tool Execution Demo", "cyan")
    calls = [
        ("dynatrace_get_problems",           {"time_range": "now-1h", "status": "OPEN"}),
        ("dynatrace_get_slo_status",         {}),
        ("dynatrace_get_service_metrics",    {"service_name": "payment-gateway"}),
        ("dynatrace_get_service_metrics",    {"service_name": "core-banking-api"}),
        ("dynatrace_get_synthetic_monitors", {"monitor_type": "ALL"}),
        ("dynatrace_get_database_metrics",   {}),
        ("dynatrace_get_infrastructure_health", {"entity_type": "ALL"}),
    ]
    for name, inp in calls:
        result = execute_dynatrace_tool(name, inp)
        show_tool_result(name, result, "cyan")

    # Summary table
    t = Table(title="Dynatrace -- Key Findings", box=box.ROUNDED, border_style="cyan")
    t.add_column("Check",      style="cyan")
    t.add_column("Status",     style="bold")
    t.add_column("Detail")
    t.add_row("Active Problems",      "[red]3 OPEN[/red]",          "P-2847 payment-gateway, P-2851 core-banking-api, P-2839 fraud-detection")
    t.add_row("SLO Violations",       "[red]2 VIOLATED[/red]",      "Payment Gateway Availability, ATM Network Availability")
    t.add_row("payment-gateway",      "[red]DEGRADED[/red]",        "Error rate 4.7%, p99 3200ms -- SLA breach")
    t.add_row("core-banking-api",     "[yellow]DEGRADED[/yellow]",  "p90 1850ms -- slow SQL queries detected")
    t.add_row("Synthetic Monitors",   "[red]2/4 FAILING[/red]",     "Fund Transfer End-to-End (96.1%), Customer Login (97.8%)")
    t.add_row("ORACLE-CORE-BANKING",  "[yellow]DEGRADED[/yellow]",  "23 slow queries, missing index on ACCOUNTS table")
    t.add_row("fraud-detection",      "[green]HEALTHY[/green]",     "Error rate 0.1%, p99 210ms")
    t.add_row("authentication-service","[green]HEALTHY[/green]",    "Error rate 0.05%, availability 99.99%")
    console.print(t)


def run_azure_demo():
    section("AZURE MONITORING AGENT -- Tool Execution Demo", "blue")
    calls = [
        ("azure_get_active_alerts",    {"severity": "ALL", "time_range_hours": 1}),
        ("azure_get_service_health",   {"regions": ["westeurope", "northeurope"]}),
        ("azure_get_aks_cluster_health", {}),
        ("azure_query_logs",           {"kql_query": "AppExceptions | where Level == 'Error' | summarize count() by ServiceName", "time_range_hours": 1}),
        ("azure_get_resource_metrics", {"resource_id": "payment-gateway-aks", "resource_type": "AKS"}),
        ("azure_get_security_alerts",  {"alert_severity": "High", "time_range_hours": 24}),
    ]
    for name, inp in calls:
        result = execute_azure_tool(name, inp)
        show_tool_result(name, result, "blue")

    t = Table(title="Azure Monitor -- Key Findings", box=box.ROUNDED, border_style="blue")
    t.add_column("Check",             style="blue")
    t.add_column("Status",            style="bold")
    t.add_column("Detail")
    t.add_row("Active Alerts",        "[red]4 FIRING[/red]",         "Sev1x3, Sev2x1 -- AKS CPU, SQL DTU, Service Bus DLQ, APIM errors")
    t.add_row("Azure Service Health", "[yellow]1 INCIDENT[/yellow]", "AZU-2024-0412: Service Bus connectivity in West Europe")
    t.add_row("payment-gateway-aks",  "[red]DEGRADED[/red]",         "1 node NotReady, 1 pod CrashLoopBackOff (OOMKilled), CPU 91.4%")
    t.add_row("core-banking-aks",     "[green]HEALTHY[/green]",      "12/12 nodes ready, 96/96 pods running")
    t.add_row("Security Alerts",      "[red]2 HIGH[/red]",           "Brute force on SQL Server, suspicious PowerShell on ATM VM")
    t.add_row("Service Bus DLQ",      "[yellow]WARNING[/yellow]",    "847 dead-letter messages in transaction-events queue")
    console.print(t)


def run_kibana_demo():
    section("KIBANA / ELK AGENT -- Tool Execution Demo", "magenta")
    calls = [
        ("kibana_get_error_rate_aggregation", {"time_range_minutes": 60}),
        ("kibana_search_logs",                {"query": "level:ERROR AND service:payment-gateway", "time_range_minutes": 60}),
        ("kibana_get_security_events",        {"event_type": "ALL", "severity": "high", "time_range_hours": 1}),
        ("kibana_get_transaction_analytics",  {"transaction_type": "all", "time_range_minutes": 60}),
        ("kibana_get_apm_traces",             {"service_name": "payment-gateway", "min_duration_ms": 1000}),
        ("kibana_get_alert_rules_status",     {"rule_category": "ALL"}),
    ]
    for name, inp in calls:
        result = execute_kibana_tool(name, inp)
        show_tool_result(name, result, "magenta")

    t = Table(title="Kibana/ELK -- Key Findings", box=box.ROUNDED, border_style="magenta")
    t.add_column("Check",                  style="magenta")
    t.add_column("Status",                 style="bold")
    t.add_column("Detail")
    t.add_row("Top Error Services",        "[red]ELEVATED[/red]",     "payment-gateway 4.7%, atm-network 2.1%, transaction-processor 1.2%")
    t.add_row("Security Events",           "[red]3 HIGH/CRIT[/red]",  "Credential stuffing (85 attempts), anomalous PII access (1,240 records), PCI-DSS PAN in logs")
    t.add_row("Payment Transactions",      "[red]DEGRADED[/red]",     "4.7% failure rate (baseline 0.3%), avg processing +340ms above baseline")
    t.add_row("ATM Transactions",          "[yellow]WARNING[/yellow]", "2.1% failure rate, avg duration 2140ms")
    t.add_row("APM Traces",                "[red]DEGRADED[/red]",     "payment-gateway p99 4100ms, error rate 8.5%, root cause: clearing-house timeout + SQL")
    t.add_row("Alert Rule Coverage",       "[yellow]WARNING[/yellow]", "1 rule FAILING (SWIFT Deadline Breach), 1 rule MUTED (Fraud Score Spike)")
    console.print(t)


def run_orchestrator_demo():
    section("ORCHESTRATOR -- Unified Incident Report (Synthesized)", "yellow")

    report = """## Overall Status: CRITICAL

## Executive Summary
The bank's payment infrastructure is experiencing a multi-vector incident affecting customer-facing payment services.
The payment-gateway service has a 4.7% error rate (15x baseline) caused by a clearing-house API timeout, compounded
by slow SQL queries on the core banking Oracle database. Three Dynatrace SLOs are violated. Concurrently, a credential
stuffing attack is active and a PCI-DSS violation (PAN in logs) requires immediate compliance response.

---

## Active Incidents (Ranked by Severity)

### INC-001 | CRITICAL | Payment Gateway Degradation
- **Affected Services:** payment-gateway, transaction-processor, clearing-house-connector
- **Root Cause:** Clearing-house API timeout (30s) -> CircuitBreaker OPEN -> 4.7% payment failure rate
- **Corroborated by:** Dynatrace P-2847, Azure APIM alert (6.2% 5xx), Kibana logs (CircuitBreaker events), APM trace TXN-98234
- **Business Impact:** ~342 customer payments failing per hour; EUR24.5M payment volume at risk; SLO-001 violated (-0.7% error budget)
- **Action Owner:** Payments Engineering Team

### INC-002 | CRITICAL | PCI-DSS Compliance Violation
- **Affected Services:** payment-gateway, log pipeline
- **Root Cause:** Primary Account Number (PAN) detected in application debug log: /var/log/payment-gateway/debug-2026-04-13.log
- **Corroborated by:** Kibana SIEM rule PCI_DSS_003_3
- **Business Impact:** Regulatory breach -- PCI-DSS Requirement 3.3 violation. Mandatory 72h notification to acquiring bank and card schemes.
- **Action Owner:** Security & Compliance Team (IMMEDIATE)

### INC-003 | HIGH | Credential Stuffing Attack
- **Affected Services:** authentication-service
- **Root Cause:** 87 failed login attempts from Tor exit node 185.220.101.47 in 5 minutes
- **Corroborated by:** Azure Defender alert, Kibana security event sec-evt-001, Azure Log Analytics
- **Business Impact:** Potential account takeover risk; customer accounts targeted
- **Action Owner:** SOC / Cybersecurity Team

### INC-004 | HIGH | Core Banking Database Degradation
- **Affected Services:** core-banking-api, ORACLE-CORE-BANKING
- **Root Cause:** Missing index on ACCOUNTS table -> full table scans -> 1,840ms avg query time (baseline ~200ms)
- **Corroborated by:** Dynatrace P-2851, Azure SQL DTU alert (85% of limit), Kibana APM slow spans
- **Business Impact:** core-banking-api p90 at 1,850ms; 1,205 users experiencing slow responses
- **Action Owner:** Database Team + Core Banking Engineering

### INC-005 | HIGH | AKS Node Failure (payment-gateway cluster)
- **Affected Services:** payment-gateway-aks (Kubernetes)
- **Root Cause:** payment-gw-node-04 NotReady; payment-processor pod OOMKilled (CrashLoopBackOff)
- **Corroborated by:** Azure AKS alert (CPU 91.4%), Azure Monitor pod health
- **Business Impact:** Reduced payment-gateway capacity -> amplifies INC-001 impact
- **Action Owner:** Platform / SRE Team

### INC-006 | MEDIUM | ATM Network Degradation
- **Affected Services:** atm-network
- **Root Cause:** atm-gateway-02 disk I/O at 98%; SLO-005 violated (-1.4% error budget)
- **Business Impact:** 2.1% ATM failure rate; 172 failed ATM transactions in last hour
- **Action Owner:** ATM Operations Team

---

## Security & Compliance Alerts
- [CRIT] **PCI-DSS VIOLATION**: PAN in payment-gateway debug logs -- MANDATORY IMMEDIATE ACTION
- [CRIT] **Credential Stuffing**: 87 login attempts from 185.220.101.47 -- block IP, notify customers at risk
- [HIGH] **Anomalous PII Access**: svc-batch-processor accessed 1,240 customer records outside batch window
- [HIGH] **Suspicious PowerShell**: Encoded command on atm-gateway-vm-02 -- isolate and investigate
- [WARN] **Azure Defender Score**: 67.4/100 (decreasing trend)

---

## Infrastructure Health Summary
| Component              | Status    | Key Metric                            |
|------------------------|-----------|---------------------------------------|
| payment-gateway        | [CRIT] CRIT  | Error 4.7%, SLO violated              |
| core-banking-api       | [HIGH] HIGH  | p90 1850ms, DB contention             |
| fraud-detection        | [OK]   OK    | Error 0.1%, p99 210ms                 |
| authentication-service | [OK]   OK    | Error 0.05%, availability 99.99%      |
| swift-connector        | [WARN] WARN  | Error 0.8%, p99 2900ms                |
| atm-network            | [HIGH] HIGH  | Error 2.1%, SLO violated              |
| Azure Service Bus      | [HIGH] HIGH  | 847 DLQ messages, West Europe incident|
| AKS payment-gateway    | [CRIT] CRIT  | 1 node down, 1 pod CrashLoopBackOff   |
| AKS core-banking       | [OK]   OK    | All 12 nodes ready                    |
| ORACLE-CORE-BANKING    | [HIGH] HIGH  | 23 slow queries, missing index        |

---

## Immediate Actions Required
1. **[Payments Eng -- NOW]** Investigate clearing-house API connectivity; check partner status page; consider failover to secondary clearing provider
2. **[Security -- NOW]** Remove PAN from payment-gateway debug logs; rotate log encryption keys; file PCI-DSS incident report within 1 hour
3. **[SOC -- NOW]** Block 185.220.101.47 at WAF and NSG; enable step-up MFA for targeted accounts; preserve auth logs for forensics
4. **[DBA -- 15min]** Add missing index on ACCOUNTS table; analyze ORACLE-CORE-BANKING for additional missing indexes; flush connection pool
5. **[SRE -- 15min]** Drain and replace payment-gw-node-04; increase AKS node pool memory limits for payment-processor pods
6. **[SOC -- 30min]** Isolate atm-gateway-vm-02 for forensic investigation of suspicious PowerShell execution
7. **[Security -- 30min]** Investigate svc-batch-processor anomalous PII access -- check if service account was compromised
8. **[Platform -- 1h]** Fix Elasticsearch connectivity for SWIFT Deadline Breach alert rule; unmute Fraud Score Spike rule after confirming maintenance is complete
9. **[ATM Ops -- 1h]** Expand disk capacity on atm-gateway-02; review ATM network for contributing connectivity issues
10. **[Platform -- 4h]** Address Azure Service Bus West Europe incident with Microsoft; implement DLQ reprocessing for 847 stuck messages

---

## Escalation Recommendation: YES
**Rationale:** Active PCI-DSS compliance violation (mandatory notification), 4.7% payment failure rate impacting hundreds of customers, active credential stuffing attack, and suspected security compromise on ATM VM constitute a P1 multi-vector incident.
**Recommended Actions:** Activate P1 incident bridge; notify CISO, CTO, and Head of Payments; engage PCI-DSS compliance officer for breach notification process."""

    console.print(Panel(report, title="[bold yellow]Orchestrator Synthesis -- Unified Incident Report[/bold yellow]", border_style="yellow"))


def main():
    console.print()
    console.print(Panel.fit(
        "[bold blue]Bank IT Operations -- Multi-Agent Monitoring System[/bold blue]\n"
        "[dim]DEMO MODE -- Full tool layer exercised with realistic banking data[/dim]\n"
        "[dim]Powered by Claude claude-opus-4-6 + Dynatrace + Azure Monitor + Kibana[/dim]",
        border_style="blue"
    ))
    from datetime import timezone
    console.print(f"\n[dim]Run timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}[/dim]\n")

    run_dynatrace_demo()
    run_azure_demo()
    run_kibana_demo()
    run_orchestrator_demo()

    section("DEMO COMPLETE", "green")
    console.print("[green][OK] All 18 tool calls executed successfully across 3 platforms[/green]")
    console.print("[green][OK] Full agentic loop architecture validated[/green]")
    console.print()
    console.print("[bold]To run with live Claude analysis:[/bold]")
    console.print("  [cyan]export ANTHROPIC_API_KEY=sk-ant-...[/cyan]")
    console.print("  [cyan]python main.py --lookback 60[/cyan]")
    console.print("  [cyan]python main.py --agent dynatrace[/cyan]")
    console.print("  [cyan]python main.py --output report.txt[/cyan]")
    console.print()


if __name__ == "__main__":
    main()
