# Bank IT Operations — Multi-Agent Monitoring System

An AI-powered monitoring system for banking IT operations that integrates **Dynatrace**, **Azure Monitor**, and **Kibana/ELK** through a multi-agent architecture built on **Claude claude-opus-4-6**. Three specialist AI agents investigate their respective platforms in parallel, and a fourth orchestrator agent synthesizes their reports into a unified incident summary.

A **live demo dashboard** is included that requires no external credentials — all platform APIs are mocked with realistic, time-varying banking data.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Quick Start — Demo Dashboard](#quick-start--demo-dashboard)
4. [Quick Start — Full Agent System](#quick-start--full-agent-system)
5. [Configuration Reference](#configuration-reference)
6. [Data Models](#data-models)
7. [Agents](#agents)
   - [Dynatrace Agent](#dynatrace-agent)
   - [Azure Monitor Agent](#azure-monitor-agent)
   - [Kibana/ELK Agent](#kibanaelk-agent)
   - [Orchestrator Agent](#orchestrator-agent)
8. [Tool Catalogue](#tool-catalogue)
   - [Dynatrace Tools (6)](#dynatrace-tools)
   - [Azure Monitor Tools (6)](#azure-monitor-tools)
   - [Kibana Tools (6)](#kibana-tools)
9. [Dashboard](#dashboard)
   - [Flask API Endpoints](#flask-api-endpoints)
   - [Frontend Components](#frontend-components)
10. [CLI Reference](#cli-reference)
11. [Replacing Mock Data with Real APIs](#replacing-mock-data-with-real-apis)
12. [Banking Services Reference](#banking-services-reference)
13. [Extending the System](#extending-the-system)

---

## Architecture Overview

```
                        ┌─────────────────────────────────────┐
                        │         run_orchestrator()          │
                        │   Claude claude-opus-4-6 + Adaptive Thinking    │
                        │   "Head of IT Operations" persona   │
                        └────────────┬───────────────────────┘
                                     │ ThreadPoolExecutor (max_workers=3)
              ┌──────────────────────┼─────────────────────┐
              │                      │                     │
   ┌──────────▼──────────┐ ┌─────────▼──────────┐ ┌───────▼──────────────┐
   │  DynatraceAgent     │ │   AzureAgent        │ │   KibanaAgent        │
   │  Claude claude-opus-4-6         │ │   Claude claude-opus-4-6       │ │   Claude claude-opus-4-6        │
   │  "Senior Dynatrace  │ │  "Senior Azure      │ │  "Senior Log/SIEM   │
   │   Engineer" persona │ │   Ops Engineer"     │ │   Engineer" persona  │
   └──────────┬──────────┘ └─────────┬──────────┘ └───────┬──────────────┘
              │                      │                     │
   ┌──────────▼──────────┐ ┌─────────▼──────────┐ ┌───────▼──────────────┐
   │  dynatrace_tools.py │ │  azure_tools.py     │ │  kibana_tools.py     │
   │  6 tool definitions │ │  6 tool definitions │ │  6 tool definitions  │
   │  + mock executors   │ │  + mock executors   │ │  + mock executors    │
   └─────────────────────┘ └────────────────────┘ └──────────────────────┘
```

### How It Works

**Phase 1 — Concurrent specialist investigation:**
The orchestrator spawns all three sub-agents simultaneously using `ThreadPoolExecutor`. Each agent runs an independent agentic loop where Claude calls its platform tools, evaluates results, and decides on follow-up calls until it has enough information to write a report.

**Phase 2 — Synthesis:**
The orchestrator Claude instance receives all three `AgentReport` objects (passed as tool results when it calls `run_dynatrace_analysis`, `run_azure_analysis`, and `run_kibana_analysis`). It cross-correlates findings, identifies shared root causes, ranks incidents by business impact, and produces a unified report.

**Agentic Loop Pattern (all four agents):**
```python
while True:
    response = client.messages.create(
        model="claude-opus-4-6",
        thinking={"type": "adaptive"},
        tools=PLATFORM_TOOLS,
        messages=messages,
    )
    messages.append({"role": "assistant", "content": response.content})
    if response.stop_reason == "end_turn":
        break
    # Execute tool calls and append results
    tool_results = [execute_tool(block) for block in response.content if block.type == "tool_use"]
    messages.append({"role": "user", "content": tool_results})
```

---

## Project Structure

```
bank_monitoring/
├── .env                          # Your secrets (not committed)
├── .env.example                  # Template for .env
├── requirements.txt              # Python dependencies
├── config.py                     # Dataclass-based config (reads from .env)
│
├── models/
│   └── alerts.py                 # Shared dataclasses: Alert, AgentReport, MonitoringReport
│
├── tools/
│   ├── dynatrace_tools.py        # 6 Dynatrace tool schemas + mock executors
│   ├── azure_tools.py            # 6 Azure Monitor tool schemas + mock executors
│   └── kibana_tools.py           # 6 Kibana tool schemas + mock executors
│
├── agents/
│   ├── dynatrace_agent.py        # Dynatrace specialist agent
│   ├── azure_agent.py            # Azure Monitor specialist agent
│   ├── kibana_agent.py           # Kibana/ELK specialist agent
│   └── orchestrator.py           # Orchestrator: runs agents + synthesizes
│
├── dashboard/
│   ├── app.py                    # Flask backend (11 JSON API endpoints)
│   └── templates/
│       └── index.html            # Single-page dark ops dashboard (Chart.js)
│
├── main.py                       # CLI entry point (requires ANTHROPIC_API_KEY)
└── demo.py                       # Demo runner — no API key required
```

---

## Quick Start — Demo Dashboard

The dashboard requires no Anthropic API key and no external platform credentials. All data is served from mock tool executors with realistic, jittered banking metrics.

**Prerequisites:** Python 3.10+, pip

```bash
# 1. Clone / navigate to the project
cd bank_monitoring

# 2. Install dependencies
pip install -r requirements.txt
# Flask is the only additional dep needed for the dashboard
pip install flask

# 3. Start the dashboard server
python dashboard/app.py

# 4. Open your browser
# http://localhost:5000
```

The dashboard auto-refreshes every 30 seconds. Each refresh calls 8 API endpoints and re-renders all components with freshly jittered metric values.

---

## Quick Start — Full Agent System

The full system uses the Claude API to run actual AI agents. The mock tool executors are still used (no Dynatrace/Azure/Kibana credentials needed), but Claude drives the investigation logic.

```bash
# 1. Copy and fill in the .env template
cp .env.example .env
# Edit .env and set: ANTHROPIC_API_KEY=sk-ant-...

# 2. Run the full multi-agent cycle (all three agents + orchestrator)
python main.py

# 3. Other CLI options
python main.py --lookback 30           # Analyse last 30 minutes instead of 60
python main.py --agent dynatrace       # Run only the Dynatrace agent
python main.py --agent azure           # Run only the Azure Monitor agent
python main.py --agent kibana          # Run only the Kibana agent
python main.py --output report.txt     # Save the full report to a file

# 4. Demo runner (no API key — calls tool executors directly, skips AI)
python demo.py
```

---

## Configuration Reference

All configuration is loaded from environment variables via `config.py`. The singleton `config` object is imported by agents and tools.

### `.env.example`

```dotenv
# Anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...

# Dynatrace
DYNATRACE_BASE_URL=https://your-tenant.live.dynatrace.com
DYNATRACE_API_TOKEN=dt0c01.xxxxxxxxxxxx
DYNATRACE_ENV_ID=abc12345

# Azure Monitor
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-secret
AZURE_SUBSCRIPTION_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_RESOURCE_GROUP=bank-prod-rg
AZURE_LOG_WORKSPACE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Kibana / Elasticsearch
KIBANA_BASE_URL=https://kibana.bank.internal:5601
KIBANA_USERNAME=monitoring_user
KIBANA_PASSWORD=your-password
KIBANA_API_KEY=base64encodedapikey==
ELASTICSEARCH_URL=https://elasticsearch.bank.internal:9200

# Monitoring thresholds
MONITORING_LOOKBACK_MINUTES=60
CRITICAL_ERROR_RATE=5.0
WARNING_ERROR_RATE=2.0
CRITICAL_RESPONSE_MS=3000
WARNING_RESPONSE_MS=1000
```

### Config Dataclasses (`config.py`)

| Class | Fields | Purpose |
|---|---|---|
| `DynatraceConfig` | `base_url`, `api_token`, `environment_id` | Dynatrace tenant access |
| `AzureConfig` | `tenant_id`, `client_id`, `client_secret`, `subscription_id`, `resource_group`, `log_workspace_id` | Azure service principal |
| `KibanaConfig` | `base_url`, `username`, `password`, `api_key`, `elasticsearch_url` | Kibana/ES access |
| `MonitoringConfig` | thresholds + `critical_services` list | Alert thresholds |
| `AppConfig` | `anthropic_api_key`, `model`, all sub-configs | Top-level singleton |

---

## Data Models

Defined in `models/alerts.py`. All agents return typed dataclasses — no raw dicts.

### `Severity` (Enum)
```
CRITICAL > HIGH > MEDIUM > LOW > INFO
```

### `AlertStatus` (Enum)
```
OPEN | ACKNOWLEDGED | RESOLVED
```

### `Alert`
| Field | Type | Description |
|---|---|---|
| `id` | str | Unique alert identifier |
| `source` | str | `"dynatrace"` / `"azure"` / `"kibana"` |
| `severity` | Severity | Severity level |
| `title` | str | Short alert title |
| `description` | str | Full description |
| `service` | str | Affected banking service |
| `timestamp` | datetime | When alert fired |
| `status` | AlertStatus | Default: `OPEN` |
| `impact` | str | Business impact description |
| `runbook_url` | str | Link to runbook |
| `tags` | list | Free-form tags |

### `ServiceHealth`
| Field | Type | Description |
|---|---|---|
| `name` | str | Service name |
| `status` | str | `"healthy"` / `"degraded"` / `"down"` / `"unknown"` |
| `error_rate` | float | Error percentage |
| `response_time_ms` | float | Current response time |
| `availability` | float | Availability percentage |
| `active_alerts` | int | Count of open alerts |
| `last_checked` | datetime | Last health check time |

### `AgentReport`
Returned by each specialist agent (`run_dynatrace_agent`, `run_azure_agent`, `run_kibana_agent`).

| Field | Type | Description |
|---|---|---|
| `agent_name` | str | `"DynatraceAgent"` etc. |
| `platform` | str | `"Dynatrace"` / `"Azure Monitor"` / `"Kibana/ELK"` |
| `generated_at` | datetime | Report generation time |
| `alerts` | list | Structured `Alert` objects |
| `service_health` | list | `ServiceHealth` objects |
| `metrics_summary` | dict | Free-form metrics dict |
| `raw_findings` | str | Full Claude-generated text report |
| `error` | Optional[str] | Error message if agent failed |

### `MonitoringReport`
Returned by the orchestrator. Aggregates all three `AgentReport` objects.

| Field | Type | Description |
|---|---|---|
| `generated_at` | datetime | When orchestration started |
| `overall_status` | str | `"healthy"` / `"degraded"` / `"critical"` / `"unknown"` |
| `dynatrace_report` | Optional[AgentReport] | Dynatrace findings |
| `azure_report` | Optional[AgentReport] | Azure findings |
| `kibana_report` | Optional[AgentReport] | Kibana findings |
| `consolidated_alerts` | list | De-duplicated alert list |
| `incident_summary` | str | Orchestrator synthesis (markdown) |
| `recommendations` | list | Recommended actions |
| `escalation_required` | bool | Whether P1 escalation is needed |

---

## Agents

### Dynatrace Agent

**File:** `agents/dynatrace_agent.py`  
**Entry point:** `run_dynatrace_agent(lookback_minutes=60) -> AgentReport`

**Persona:** Senior Dynatrace monitoring engineer at a major commercial bank.

**Investigation strategy (encoded in system prompt):**
1. `dynatrace_get_problems` — immediate awareness of open problems
2. `dynatrace_get_slo_status` — SLO compliance and regulatory impact
3. `dynatrace_get_service_metrics` — metrics for any flagged services
4. `dynatrace_get_synthetic_monitors` — customer-facing impact assessment
5. `dynatrace_get_database_metrics` — if application issues are detected
6. `dynatrace_get_infrastructure_health` — resource bottleneck identification

**Output:** A prioritized text report with metric values, SLA breach status, and numbered remediation actions. The raw text is stored in `AgentReport.raw_findings`.

---

### Azure Monitor Agent

**File:** `agents/azure_agent.py`  
**Entry point:** `run_azure_agent(lookback_minutes=60) -> AgentReport`

**Persona:** Senior Azure cloud operations engineer at a major commercial bank.

**Resources monitored:**
- AKS clusters: `payment-gateway-aks`, `core-banking-aks`
- Azure SQL: `core-banking-sqlserver`
- Service Bus: `bank-servicebus`
- API Management: `bank-apim`
- Azure AD, Key Vault, Storage, VNets

**Investigation strategy:**
1. `azure_get_active_alerts` — immediate alert triage
2. `azure_get_service_health` — platform-level Azure incidents
3. `azure_get_aks_cluster_health` — Kubernetes workload health
4. `azure_query_logs` — KQL queries for errors and anomalies
5. `azure_get_resource_metrics` — deep-dive on flagged resources
6. `azure_get_security_alerts` — Defender for Cloud threat detections

---

### Kibana/ELK Agent

**File:** `agents/kibana_agent.py`  
**Entry point:** `run_kibana_agent(lookback_minutes=60) -> AgentReport`

**Persona:** Senior log analytics and SIEM engineer at a major commercial bank.

**Log sources monitored:**
- Application logs (all microservices)
- Security/SIEM (authentication, access, privilege events)
- Transaction logs (payments, SWIFT, ATM)
- APM distributed traces
- Audit logs (PCI-DSS, GDPR compliance)

**Investigation strategy:**
1. `kibana_get_error_rate_aggregation` — identify error hotspots across services
2. `kibana_search_logs` — targeted log search for top-offending services
3. `kibana_get_security_events` — credential stuffing, PCI violations, anomalous access
4. `kibana_get_transaction_analytics` — payment/transfer failure rates and anomalies
5. `kibana_get_apm_traces` — distributed traces for slow/failing transactions
6. `kibana_get_alert_rules_status` — check for muted or broken detection rules

---

### Orchestrator Agent

**File:** `agents/orchestrator.py`  
**Entry point:** `run_orchestrator(lookback_minutes=60) -> MonitoringReport`

**Persona:** Head of IT Operations at a major commercial bank.

**Execution model:**
```
Phase 1: ThreadPoolExecutor launches all 3 sub-agents concurrently
         ├── run_dynatrace_agent()   ──┐
         ├── run_azure_agent()       ──┼── parallel execution
         └── run_kibana_agent()      ──┘
Phase 2: Orchestrator Claude receives all 3 AgentReports as tool results
         └── Synthesizes into unified MonitoringReport
```

**Synthesis responsibilities:**
- **Correlate** findings — e.g., payment-gateway errors appearing in all three platforms = one incident, not three
- **Rank** incidents by business impact (customer impact, financial risk, regulatory exposure)
- **Identify root causes** — distinguish symptoms from causes
- **Security triage** — elevate PCI violations and credential attacks to top priority
- **Escalation decision** — determine if P1 incident bridge or executive notification is required

**Report structure produced:**
```markdown
## Overall Status: [HEALTHY|DEGRADED|CRITICAL]
## Executive Summary
## Active Incidents (ranked by severity)
## Security & Compliance Alerts
## Infrastructure Health Summary
## Immediate Actions Required
## Escalation Recommendation
```

**Status extraction:** The orchestrator parses the final text for `"OVERALL STATUS: CRITICAL"` / `"DEGRADED"` / `"HEALTHY"` to populate `MonitoringReport.overall_status`. Escalation is detected from `"ESCALATION RECOMMENDATION: YES"`.

---

## Tool Catalogue

### Dynatrace Tools

Defined in `tools/dynatrace_tools.py` as `DYNATRACE_TOOLS` (list of Anthropic tool schemas).  
Executed via `execute_dynatrace_tool(tool_name, tool_input) -> str` (returns JSON string).

| Tool | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `dynatrace_get_problems` | Fetch open/recent problems | `time_range`, `status`, `severity` | Problem list with root causes, affected entities, impacted user counts |
| `dynatrace_get_service_metrics` | Response time, error rate, throughput for one service | `service_name`, `time_range` | p50/p90/p99 ms, error rate %, throughput/min, availability %, SLA breach flags |
| `dynatrace_get_infrastructure_health` | Host CPU/memory/disk across all production hosts | `entity_type`, `tag_filter` | Critical host list, process group health, summary counts |
| `dynatrace_get_slo_status` | SLO compliance and error budget | `slo_ids` (optional) | Target vs current %, error budget remaining %, burn rate, status (OK/WARNING/VIOLATED) |
| `dynatrace_get_synthetic_monitors` | Customer journey test results | `monitor_type`, `time_range` | Availability %, failed check count, last failure reason per monitor |
| `dynatrace_get_database_metrics` | DB query times, pool usage, slow queries | `database_name` (optional) | Avg query time ms, slow query count, connection pool %, lock waits, replication lag |

**Mock data highlights:**
- `payment-gateway`: 4.7% error rate, p99=3200ms (SLA breach), synthetics failing
- `core-banking-api`: p90=1850ms, p99=4100ms (SLA breach), ORACLE DB has 23 slow queries
- `fraud-detection`: CPU saturation (94.2%) on `fraud-ml-node-01`
- `atm-network`: 2.1% error rate, SLO-005 violated (97.8% vs 99.5% target)

---

### Azure Monitor Tools

Defined in `tools/azure_tools.py` as `AZURE_TOOLS`.  
Executed via `execute_azure_tool(tool_name, tool_input) -> str`.

| Tool | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `azure_get_active_alerts` | Active Monitor alerts across the subscription | `severity`, `resource_group`, `time_range_hours` | Alert list with condition, fired time, monitor condition (Fired/Resolved) |
| `azure_get_resource_metrics` | Metrics for a specific Azure resource | `resource_id`, `resource_type` | Type-specific metrics (CPU%, DTU%, pod counts, request rates, etc.) |
| `azure_query_logs` | KQL query against Log Analytics workspace | `kql_query`, `time_range_hours` | Row results with timestamps, levels, messages. Routes to error/security/general mock based on keywords |
| `azure_get_aks_cluster_health` | Node/pod health for AKS clusters | `cluster_name` (optional) | Node ready/notReady counts, pod running/pending/failed, recent events |
| `azure_get_security_alerts` | Defender for Cloud alerts | `alert_severity`, `time_range_hours` | Threat detections with remediation steps, Secure Score |
| `azure_get_service_health` | Azure platform incidents and maintenance | `regions` | Active incidents, planned maintenance, health advisories |

**Mock data highlights:**
- `payment-gateway-aks`: 1 node NotReady, 1 pod in CrashLoopBackOff (OOMKilled), 2 pods pending
- `core-banking-sqlserver`: DTU at 87% (approaching limit), brute-force attack from 185.220.101.0/24
- `bank-servicebus`: 847 dead-letter messages in `transaction-events` queue
- Azure Service Health: active `Service Bus -- Intermittent connectivity` incident in West Europe

---

### Kibana Tools

Defined in `tools/kibana_tools.py` as `KIBANA_TOOLS`.  
Executed via `execute_kibana_tool(tool_name, tool_input) -> str`.

| Tool | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `kibana_search_logs` | Lucene/KQL log search across ES indices | `query`, `index_pattern`, `time_range_minutes`, `max_results` | Matching log entries with @timestamp, level, service, message, traceId |
| `kibana_get_error_rate_aggregation` | Error % by service over a time window | `time_range_minutes`, `service_filter` | Error/warning/total counts + errorRate % per service, top error services |
| `kibana_get_security_events` | SIEM events: auth failures, PCI violations, anomalous access | `event_type`, `severity`, `time_range_hours` | Events with sourceIp, userId, description, threat level |
| `kibana_get_transaction_analytics` | Transaction volumes and failure rates | `transaction_type`, `time_range_minutes` | Per-type: total/successful/failed, failureRate, EUR value, anomalies |
| `kibana_get_alert_rules_status` | Kibana alerting rule health check | `rule_category` | Rule status (active/muted/error), last execution, fires-per-hour, failure reasons |
| `kibana_get_apm_traces` | Distributed traces for slow/failed transactions | `service_name`, `transaction_name`, `time_range_minutes`, `min_duration_ms` | Span breakdown, slow span identification, root cause, trace statistics |

**Mock data highlights:**
- `payment-gateway`: 4.70% error rate (5,189 errors/hr), CircuitBreaker OPEN for clearing-house-api
- Security: PAN (Primary Account Number) detected in debug log (PCI-DSS Req 3.3 violation)
- Security: Credential stuffing from Tor exit node 185.220.101.47 (87 attempts)
- Security: `svc-batch-processor` accessed 1,240 customer PII records outside batch window
- Transaction: EUR 24.5M in-flight payments at risk (4.7% failure rate)
- APM trace shows `debit_account` span taking 1840ms + clearing-house-connector timeout causing 3840ms total

---

## Dashboard

### Flask API Endpoints

**Server:** `dashboard/app.py`  
**Start:** `python dashboard/app.py` (serves on `0.0.0.0:5000`)

| Method | Endpoint | Description | Response keys |
|---|---|---|---|
| GET | `/` | Serves the dashboard HTML | HTML |
| GET | `/api/services` | 8 banking services with live-jittered metrics | `overall`, `services[]`, `summary` |
| GET | `/api/alerts` | 13 cross-platform correlated alerts | `alerts[]`, `counts` |
| GET | `/api/slos` | 5 SLOs with burn rates and budget % | `slos[]` |
| GET | `/api/orchestrator` | Unified incident report (6 incidents) | `incidents[]`, `immediate_actions[]`, `overall_status`, `escalation_required` |
| GET | `/api/charts/error-rates` | 12-point 60-min error rate history per service | `labels[]`, `datasets[]` |
| GET | `/api/charts/response-times` | Current p50/p90/p99 per service | `services[]` |
| GET | `/api/charts/transaction-volume` | 60-min transaction volume by type | `labels[]`, `datasets[]` |
| GET | `/api/charts/infrastructure` | Host CPU and memory utilization | `hosts[]` |
| GET | `/api/dynatrace` | Full raw Dynatrace tool data | `problems`, `slos`, `infra`, `synthetics`, `databases` |
| GET | `/api/azure` | Full raw Azure tool data | `alerts`, `service_health`, `aks`, `security` |
| GET | `/api/kibana` | Full raw Kibana tool data | `error_rates`, `security_events`, `transactions`, `alert_rules` |

**Jitter function:** All numeric metrics are passed through `_jitter(base, pct=0.08)` which applies ±8% random variation on each request. This makes the dashboard feel live — charts animate on each 30-second refresh without requiring real data changes.

```python
def _jitter(base, pct=0.08):
    return round(base * (1 + random.uniform(-pct, pct)), 2)
```

**Chart data format:** All chart endpoints return `{labels: [...], datasets: [{label, data, color}, ...]}` which maps directly to Chart.js dataset format.

---

### Frontend Components

**File:** `dashboard/templates/index.html` (~1,000 lines, pure vanilla JS + CSS)  
**Charts:** Chart.js 4.4.0 (CDN, no build step)  
**Theme:** Dark ops dashboard — `#0b1120` background, `#1a2236` cards

#### Component Map

| Section | Data Source | Update Behaviour |
|---|---|---|
| **Topbar** | — | Shows last refresh time + 30s countdown bar |
| **Agent Status Row** | `/api/dynatrace`, `/api/azure`, `/api/kibana` | Shows agent name, status badge, problem/alert counts |
| **KPI Stats Bar** | `/api/services`, `/api/alerts` | Total services, active alerts (critical/high/warning), services degraded |
| **Service Health Grid** | `/api/services` | 8 cards, colored left border by status; error rate, p90ms, availability, SLO badge |
| **Error Rate Chart** | `/api/charts/error-rates` | Line chart, 60-min history, 5 services |
| **Alert Feed** | `/api/alerts` | Scrollable list, severity badge, source tag, correlated alert IDs |
| **Response Time Chart** | `/api/charts/response-times` | Grouped bar chart, p50/p90/p99 per service |
| **SLO Compliance Table** | `/api/slos` | Table with progress bars for error budget, burn rate, status chip |
| **Transaction Volume Chart** | `/api/charts/transaction-volume` | Line chart, 4 transaction types |
| **Infrastructure Heatmap** | `/api/charts/infrastructure` | 6 hosts, dual CPU/memory bars with status color |
| **Orchestrator Panel** | `/api/orchestrator` | 6 ranked incidents (severity + root cause + owner) + immediate actions table |

#### JavaScript Architecture

```
window.DOMContentLoaded
  └── refreshAll()
       ├── Promise.all([8 fetch calls])
       ├── renderServices()
       ├── renderAlerts()
       ├── renderSLOs()
       ├── renderInfra()
       ├── renderChartErrorRate()      -- makeLineChart()
       ├── renderChartResponseTime()   -- makeBarChart()
       ├── renderChartTxnVolume()      -- makeLineChart()
       └── renderOrchestrator()
  └── startCountdown()                 -- setInterval 1s, triggers refreshAll() at 0
```

Chart instances are stored globally (`charts = {}`) and destroyed/recreated on each refresh to avoid Chart.js canvas reuse errors.

#### Status Color Coding

| Status | CSS Variable | Hex | Used For |
|---|---|---|---|
| critical | `--red` | `#ef4444` | Critical alerts, violated SLOs, critical services |
| high | `--orange` | `#f97316` | High alerts, degraded services |
| warning | `--yellow` | `#eab308` | Warnings, SLO approaching threshold |
| healthy/ok | `--green` | `#22c55e` | Healthy services, passing SLOs |
| info | `--indigo` | `#6366f1` | Info-level metrics, neutral chart lines |

---

## CLI Reference

```
python main.py [--lookback MINUTES] [--agent AGENT] [--output FILE]

Options:
  --lookback INT    Minutes of history to analyse (default: 60)
  --agent CHOICE    Which agent to run: dynatrace | azure | kibana | all (default: all)
  --output FILE     Save full report to this file path (UTF-8 text)

Examples:
  python main.py                         # Full cycle: all agents + orchestrator
  python main.py --lookback 30           # Last 30 minutes
  python main.py --agent dynatrace       # Dynatrace only
  python main.py --output report.txt     # Save to file

Requirements:
  ANTHROPIC_API_KEY must be set in .env or environment
```

**`demo.py`** — No API key needed. Calls all 18 tool executors directly and prints mock results with a pre-written orchestrator synthesis. Useful for validating tool schemas and mock data without any API calls.

---

## Replacing Mock Data with Real APIs

Each tool file contains comments indicating exactly what to replace. The pattern is the same across all three platforms:

### Dynatrace (`tools/dynatrace_tools.py`)

```python
# MOCK:
def _get_problems(time_range="now-1h", status="OPEN", severity="ALL") -> dict:
    return { "problems": [...hardcoded...] }

# REAL:
import requests
def _get_problems(time_range="now-1h", status="OPEN", severity="ALL") -> dict:
    headers = {"Authorization": f"Api-Token {config.dynatrace.api_token}"}
    resp = requests.get(
        f"{config.dynatrace.base_url}/api/v2/problems",
        headers=headers,
        params={"from": time_range, "status": status, "severityFilter": severity},
    )
    resp.raise_for_status()
    return resp.json()
```

### Azure Monitor (`tools/azure_tools.py`)

```python
# REAL (requires: pip install azure-identity azure-mgmt-monitor azure-monitor-query)
from azure.identity import ClientSecretCredential
from azure.mgmt.monitor import MonitorManagementClient

credential = ClientSecretCredential(
    config.azure.tenant_id,
    config.azure.client_id,
    config.azure.client_secret,
)
monitor_client = MonitorManagementClient(credential, config.azure.subscription_id)
```

### Kibana/Elasticsearch (`tools/kibana_tools.py`)

```python
# REAL (requires: pip install elasticsearch)
from elasticsearch import Elasticsearch

es = Elasticsearch(
    config.kibana.elasticsearch_url,
    api_key=config.kibana.api_key,
)
results = es.search(index="bank-app-logs-*", body={"query": {"match": {...}}})
```

**Swap strategy:** Replace each `_get_*` private function body while keeping the tool schema (`DYNATRACE_TOOLS`, etc.) and the executor dispatch function (`execute_*_tool`) unchanged. The agents and orchestrator never call tool executors directly — they only see the JSON schemas.

---

## Banking Services Reference

The system monitors 8 core banking services. Their mock health profiles are used consistently across all tools and the dashboard:

| Service | Priority | Normal Error Rate | p90 SLA | SLO Target | Current Status |
|---|---|---|---|---|---|
| `payment-gateway` | CRITICAL | 0.3% | 500ms | 99.9% availability | **CRITICAL** — 4.7% errors, SLO violated |
| `core-banking-api` | CRITICAL | 0.1% | 1000ms | p95 < 2s (95% of time) | **WARNING** — p90=1850ms, SLO warning |
| `fraud-detection` | HIGH | 0.05% | 100ms | p99 < 500ms | Healthy — CPU saturation on infra |
| `authentication-service` | HIGH | 0.01% | 100ms | 99.99% availability | Healthy |
| `transaction-processor` | HIGH | 0.2% | 500ms | — | **WARNING** — 1.2% error rate |
| `swift-connector` | HIGH | 0.1% | 2000ms | — | Healthy |
| `account-management` | MEDIUM | 0.1% | 500ms | — | Healthy |
| `atm-network` | MEDIUM | 0.5% | 1500ms | 99.5% availability | **HIGH** — 2.1% errors, SLO violated |

---

## Extending the System

### Adding a New Monitoring Platform

1. **Create `tools/newplatform_tools.py`** with:
   - `NEWPLATFORM_TOOLS`: list of tool JSON schemas (same format as existing tools)
   - `execute_newplatform_tool(tool_name, tool_input) -> str`: dispatcher
   - Private mock functions for each tool

2. **Create `agents/newplatform_agent.py`** with:
   - A `NEWPLATFORM_SYSTEM_PROMPT` string defining the agent's persona and investigation strategy
   - `run_newplatform_agent(lookback_minutes=60) -> AgentReport` using the standard agentic loop

3. **Add to the orchestrator** (`agents/orchestrator.py`):
   - Add a new tool to `ORCHESTRATOR_TOOLS` (`run_newplatform_analysis`)
   - Add a fourth `executor.submit()` call in `_run_sub_agents_concurrently()`
   - Handle the new tool in `_execute_orchestrator_tool()`

4. **Add a new Flask endpoint** in `dashboard/app.py` for the dashboard

### Adding a New Tool to an Existing Platform

1. Add the tool schema to the relevant `*_TOOLS` list
2. Add a handler entry in `execute_*_tool()`
3. Implement the mock function
4. The agents will automatically discover and use the new tool — no agent code changes needed

### Changing the Model or Thinking Settings

Edit `config.py`:
```python
@dataclass
class AppConfig:
    model: str = "claude-opus-4-6"  # Change model here
```

Edit the agent files to change thinking settings:
```python
response = client.messages.create(
    model=config.model,
    thinking={"type": "adaptive"},   # or {"type": "disabled"}
    max_tokens=8096,
    ...
)
```

### Adding Persistent Alert Storage

The current system is stateless — each run generates a fresh report. To add persistence:
- Store `MonitoringReport` objects in a database (SQLite, PostgreSQL)
- Add a `/api/history` endpoint to the Flask app
- Add a trend line to the dashboard comparing current vs previous runs
