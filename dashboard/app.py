"""
Bank IT Operations - Real-Time Monitoring Dashboard v2
Flask + SocketIO backend with 22 JSON API endpoints.
Run:  python dashboard/app.py
Then open: http://localhost:5000
"""
import json
import random
import sys
import os
from datetime import datetime, timedelta, timezone
from threading import Thread
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO, emit

from tools.dynatrace_tools import execute_dynatrace_tool
from tools.azure_tools     import execute_azure_tool
from tools.kibana_tools    import execute_kibana_tool

from analytics.baselines   import get_mock_anomaly_report
from analytics.correlation import get_mock_correlation_report
from analytics.forecasting import get_mock_forecasts
from analytics.burn_rate   import get_mock_burn_rate_report

from memory.store          import get_mock_memory_context
from integrations.pagerduty import get_mock_pagerduty_status
from integrations.threat_intel import get_mock_threat_summary
from runbooks.executor     import get_mock_runbook_queue
from webhooks.server       import get_mock_webhook_events, webhooks_bp
from agents.postmortem_agent import get_mock_postmortem
from tools.compliance_tools  import execute_compliance_tool
from tools.cost_tools        import execute_cost_tool

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "bank-ops-dashboard-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Register webhook blueprint
app.register_blueprint(webhooks_bp)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jitter(base, pct=0.08):
    return round(base * (1 + random.uniform(-pct, pct)), 2)

def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# WebSocket -- push live metric updates every 10s
# ---------------------------------------------------------------------------

def _background_push():
    """Push small metric updates to connected clients every 10 seconds."""
    while True:
        time.sleep(10)
        try:
            snapshot = {
                "type":         "metrics_update",
                "timestamp":    _now().isoformat(),
                "payment_error_rate": _jitter(4.70),
                "atm_error_rate":     _jitter(2.10),
                "core_p90":           _jitter(1850),
                "fraud_cpu":          _jitter(94.2, 0.03),
                "active_alerts":      13,
                "slo_violated":       2,
            }
            socketio.emit("metrics_update", snapshot)
        except Exception:
            pass


@socketio.on("connect")
def on_connect():
    print("  [WS] Client connected")
    emit("connected", {"message": "Bank IT Ops Dashboard connected", "timestamp": _now().isoformat()})


@socketio.on("disconnect")
def on_disconnect():
    print("  [WS] Client disconnected")


# ---------------------------------------------------------------------------
# API -- Core monitoring (existing)
# ---------------------------------------------------------------------------

@app.route("/api/services")
def api_services():
    services = [
        {"name": "payment-gateway",       "status": "critical", "error_rate": _jitter(4.70), "p90_ms": _jitter(890),  "p99_ms": _jitter(3200), "availability": _jitter(98.2,  0.01), "throughput": _jitter(1840), "slo_status": "violated",  "source": "dynatrace+kibana"},
        {"name": "core-banking-api",       "status": "warning",  "error_rate": _jitter(0.30), "p90_ms": _jitter(1850), "p99_ms": _jitter(4100), "availability": _jitter(99.7,  0.01), "throughput": _jitter(3120), "slo_status": "warning",   "source": "dynatrace"},
        {"name": "fraud-detection",        "status": "healthy",  "error_rate": _jitter(0.10), "p90_ms": _jitter(95),   "p99_ms": _jitter(210),  "availability": _jitter(99.9,  0.01), "throughput": _jitter(9800), "slo_status": "ok",        "source": "dynatrace"},
        {"name": "authentication-service", "status": "healthy",  "error_rate": _jitter(0.05), "p90_ms": _jitter(65),   "p99_ms": _jitter(120),  "availability": _jitter(99.99, 0.01), "throughput": _jitter(14300),"slo_status": "ok",        "source": "dynatrace"},
        {"name": "transaction-processor",  "status": "warning",  "error_rate": _jitter(1.20), "p90_ms": _jitter(720),  "p99_ms": _jitter(1800), "availability": _jitter(99.4,  0.01), "throughput": _jitter(2450), "slo_status": "ok",        "source": "dynatrace"},
        {"name": "swift-connector",        "status": "healthy",  "error_rate": _jitter(0.80), "p90_ms": _jitter(1200), "p99_ms": _jitter(2900), "availability": _jitter(99.5,  0.01), "throughput": _jitter(340),  "slo_status": "ok",        "source": "dynatrace"},
        {"name": "account-management",     "status": "healthy",  "error_rate": _jitter(0.20), "p90_ms": _jitter(450),  "p99_ms": _jitter(980),  "availability": _jitter(99.8,  0.01), "throughput": _jitter(5600), "slo_status": "ok",        "source": "dynatrace"},
        {"name": "atm-network",            "status": "high",     "error_rate": _jitter(2.10), "p90_ms": _jitter(1900), "p99_ms": _jitter(5200), "availability": _jitter(97.8,  0.01), "throughput": _jitter(820),  "slo_status": "violated",  "source": "dynatrace+kibana"},
    ]
    critical = sum(1 for s in services if s["status"] == "critical")
    high     = sum(1 for s in services if s["status"] == "high")
    warning  = sum(1 for s in services if s["status"] == "warning")
    healthy  = sum(1 for s in services if s["status"] == "healthy")
    overall  = "critical" if critical > 0 else ("high" if high > 0 else ("warning" if warning > 0 else "healthy"))
    return jsonify({"overall": overall, "services": services,
                    "summary": {"critical": critical, "high": high, "warning": warning, "healthy": healthy}})


@app.route("/api/alerts")
def api_alerts():
    now = _now()
    alerts = [
        {"id": "DT-P2847",  "source": "Dynatrace", "severity": "critical", "category": "availability",  "title": "High failure rate on payment-gateway /v2/transfers",         "service": "payment-gateway",        "age_min": 23,  "correlated": ["AZ-003", "KB-TXN"]},
        {"id": "DT-P2851",  "source": "Dynatrace", "severity": "high",     "category": "performance",   "title": "Response time degradation on core-banking-api",              "service": "core-banking-api",       "age_min": 8,   "correlated": ["AZ-002", "KB-APM"]},
        {"id": "DT-P2839",  "source": "Dynatrace", "severity": "high",     "category": "resource",      "title": "fraud-detection service CPU saturation (94%)",               "service": "fraud-detection",        "age_min": 45,  "correlated": []},
        {"id": "AZ-001",    "source": "Azure",     "severity": "high",     "category": "compute",       "title": "AKS node NotReady + pod CrashLoopBackOff (OOMKilled)",       "service": "payment-gateway-aks",    "age_min": 18,  "correlated": ["DT-P2847"]},
        {"id": "AZ-002",    "source": "Azure",     "severity": "high",     "category": "database",      "title": "Azure SQL DTU approaching limit (87%) -- core-banking-db",   "service": "core-banking-sqlserver", "age_min": 31,  "correlated": ["DT-P2851"]},
        {"id": "AZ-003",    "source": "Azure",     "severity": "warning",  "category": "messaging",     "title": "Service Bus DLQ growing: 847 messages in transaction-events", "service": "bank-servicebus",        "age_min": 12,  "correlated": ["DT-P2847"]},
        {"id": "AZ-SEC1",   "source": "Azure",     "severity": "critical", "category": "security",      "title": "Brute force attack on Azure SQL -- 185.220.101.47",           "service": "core-banking-sqlserver", "age_min": 120, "correlated": ["KB-SEC1"]},
        {"id": "AZ-SEC2",   "source": "Azure",     "severity": "critical", "category": "security",      "title": "Suspicious PowerShell execution on atm-gateway-vm-02",       "service": "atm-network",            "age_min": 300, "correlated": []},
        {"id": "KB-SEC1",   "source": "Kibana",    "severity": "critical", "category": "security",      "title": "Credential stuffing: 87 failed logins from Tor exit node",   "service": "authentication-service", "age_min": 42,  "correlated": ["AZ-SEC1"]},
        {"id": "KB-PCI",    "source": "Kibana",    "severity": "critical", "category": "compliance",    "title": "PCI-DSS VIOLATION: PAN detected in payment-gateway debug log","service": "payment-gateway",        "age_min": 8,   "correlated": []},
        {"id": "KB-SEC2",   "source": "Kibana",    "severity": "high",     "category": "security",      "title": "svc-batch-processor accessed 1,240 PII records outside schedule","service": "account-management",  "age_min": 15,  "correlated": []},
        {"id": "KB-TXN",    "source": "Kibana",    "severity": "high",     "category": "transactions",  "title": "Payment failure rate 4.7% (15x baseline, EUR 24.5M at risk)", "service": "payment-gateway",        "age_min": 23,  "correlated": ["DT-P2847"]},
        {"id": "KB-APM",    "source": "Kibana",    "severity": "warning",  "category": "performance",   "title": "APM: payment-gateway p99 = 4100ms, error rate 8.5%",          "service": "payment-gateway",        "age_min": 5,   "correlated": ["DT-P2847"]},
    ]
    counts = {
        "critical": sum(1 for a in alerts if a["severity"] == "critical"),
        "high":     sum(1 for a in alerts if a["severity"] == "high"),
        "warning":  sum(1 for a in alerts if a["severity"] == "warning"),
        "total":    len(alerts),
    }
    return jsonify({"alerts": alerts, "counts": counts})


@app.route("/api/slos")
def api_slos():
    slos = [
        {"id": "SLO-001", "name": "Payment Gateway Availability",  "target": 99.9,  "current": _jitter(98.2, 0.005), "budget_pct": _jitter(-0.7, 0.1),  "status": "violated",  "burn_rate": _jitter(3.2)},
        {"id": "SLO-002", "name": "Core Banking p95 < 2s",          "target": 95.0,  "current": _jitter(91.3, 0.005), "budget_pct": _jitter(12.4, 0.1), "status": "warning",   "burn_rate": _jitter(1.8)},
        {"id": "SLO-003", "name": "Auth Service Availability",       "target": 99.99, "current": _jitter(99.99,0.001), "budget_pct": _jitter(98.5, 0.1), "status": "ok",        "burn_rate": _jitter(0.02)},
        {"id": "SLO-004", "name": "Fraud Detection p99 < 500ms",     "target": 99.0,  "current": _jitter(99.7, 0.005), "budget_pct": _jitter(87.3, 0.1), "status": "ok",        "burn_rate": _jitter(0.3)},
        {"id": "SLO-005", "name": "ATM Network Availability",         "target": 99.5,  "current": _jitter(97.8, 0.005), "budget_pct": _jitter(-1.4, 0.1),  "status": "violated",  "burn_rate": _jitter(4.1)},
    ]
    return jsonify({"slos": slos})


@app.route("/api/orchestrator")
def api_orchestrator():
    return jsonify({
        "overall_status":    "critical",
        "escalation_required": True,
        "confidence_score":  0.94,
        "generated_at":      _now().isoformat(),
        "incident_count":    6,
        "slo_violations":    2,
        "security_events":   3,
        "incidents": [
            {"rank": 1, "id": "INC-001", "severity": "critical", "confidence": 0.97, "title": "Payment Gateway Degradation",     "root_cause": "Clearing-house API timeout (30s) -- CircuitBreaker OPEN", "impact": "4.7% failure rate, EUR 24.5M at risk, 342 customers/hr", "sources": ["Dynatrace", "Azure", "Kibana"], "owner": "Payments Engineering"},
            {"rank": 2, "id": "INC-002", "severity": "critical", "confidence": 0.99, "title": "PCI-DSS Compliance Violation",    "root_cause": "PAN in payment-gateway debug log (PCI-DSS Req 3.3)",    "impact": "Mandatory 72h card scheme notification", "sources": ["Kibana", "Audit"], "owner": "Security & Compliance"},
            {"rank": 3, "id": "INC-003", "severity": "critical", "confidence": 0.98, "title": "Active Credential Stuffing Attack","root_cause": "87 login attempts from Tor exit node 185.220.101.47",   "impact": "Account takeover risk", "sources": ["Azure", "Kibana"], "owner": "SOC"},
            {"rank": 4, "id": "INC-004", "severity": "high",     "confidence": 0.91, "title": "Core Banking DB Degradation",     "root_cause": "Missing index on ACCOUNTS table -- full table scans",   "impact": "1,205 users slow responses", "sources": ["Dynatrace", "Azure"], "owner": "DBA + Core Banking"},
            {"rank": 5, "id": "INC-005", "severity": "high",     "confidence": 0.88, "title": "AKS Node Failure (payment cluster)","root_cause": "payment-gw-node-04 NotReady, OOMKilled CrashLoopBackOff", "impact": "Reduced capacity, amplifies INC-001", "sources": ["Azure"], "owner": "Platform / SRE"},
            {"rank": 6, "id": "INC-006", "severity": "medium",   "confidence": 0.85, "title": "ATM Network Degradation",          "root_cause": "atm-gateway-02 disk I/O at 98%, SLO-005 violated",      "impact": "2.1% ATM failure rate", "sources": ["Dynatrace", "Kibana"], "owner": "ATM Operations"},
        ],
        "immediate_actions": [
            {"priority": 1, "team": "Payments Eng",  "urgency": "NOW",   "action": "Investigate clearing-house API; failover to secondary provider"},
            {"priority": 2, "team": "Security",      "urgency": "NOW",   "action": "Remove PAN from debug logs; file PCI-DSS incident report"},
            {"priority": 3, "team": "SOC",           "urgency": "NOW",   "action": "Block 185.220.101.47 at WAF; enable step-up MFA for targets"},
            {"priority": 4, "team": "DBA",           "urgency": "15min", "action": "Add missing index on ACCOUNTS table; flush Oracle pool"},
            {"priority": 5, "team": "SRE",           "urgency": "15min", "action": "Drain payment-gw-node-04; increase AKS pod memory limits"},
            {"priority": 6, "team": "SOC",           "urgency": "30min", "action": "Isolate atm-gateway-vm-02; begin forensic investigation"},
        ],
    })


# ---------------------------------------------------------------------------
# API -- Charts (existing + new trace waterfall)
# ---------------------------------------------------------------------------

@app.route("/api/charts/error-rates")
def api_chart_error_rates():
    now = _now()
    labels = [(now - timedelta(minutes=55 - i*5)).strftime("%H:%M") for i in range(12)]
    def _series(base, spike_at=None, spike_val=None):
        pts = []
        for i in range(12):
            v = base * (1 + random.uniform(-0.15, 0.15))
            if spike_at is not None and i >= spike_at:
                v = spike_val * (1 + random.uniform(-0.1, 0.1))
            pts.append(round(v, 2))
        return pts
    return jsonify({"labels": labels, "datasets": [
        {"label": "payment-gateway",  "data": _series(0.5, spike_at=4, spike_val=4.7),  "color": "#ef4444"},
        {"label": "atm-network",      "data": _series(0.8, spike_at=6, spike_val=2.1),  "color": "#f97316"},
        {"label": "txn-processor",    "data": _series(0.3, spike_at=7, spike_val=1.2),  "color": "#eab308"},
        {"label": "core-banking-api", "data": _series(0.3),                              "color": "#6366f1"},
        {"label": "fraud-detection",  "data": _series(0.1),                              "color": "#22c55e"},
    ]})


@app.route("/api/charts/response-times")
def api_chart_response_times():
    services = [
        {"service": "payment-gateway",  "p50": _jitter(245),  "p90": _jitter(890),  "p99": _jitter(3200)},
        {"service": "core-banking-api", "p50": _jitter(420),  "p90": _jitter(1850), "p99": _jitter(4100)},
        {"service": "txn-processor",    "p50": _jitter(310),  "p90": _jitter(720),  "p99": _jitter(1800)},
        {"service": "swift-connector",  "p50": _jitter(520),  "p90": _jitter(1200), "p99": _jitter(2900)},
        {"service": "atm-network",      "p50": _jitter(680),  "p90": _jitter(1900), "p99": _jitter(5200)},
        {"service": "account-mgmt",     "p50": _jitter(180),  "p90": _jitter(450),  "p99": _jitter(980)},
        {"service": "fraud-detection",  "p50": _jitter(38),   "p90": _jitter(95),   "p99": _jitter(210)},
        {"service": "auth-service",     "p50": _jitter(22),   "p90": _jitter(65),   "p99": _jitter(120)},
    ]
    return jsonify({"services": services})


@app.route("/api/charts/transaction-volume")
def api_chart_txn_volume():
    now = _now()
    labels = [(now - timedelta(minutes=55 - i*5)).strftime("%H:%M") for i in range(12)]
    def _vol(base, dip_at=None, dip_factor=0.6):
        pts = []
        for i in range(12):
            v = base * (1 + random.uniform(-0.08, 0.08))
            if dip_at is not None and i >= dip_at:
                v = base * dip_factor * (1 + random.uniform(-0.05, 0.05))
            pts.append(int(v))
        return pts
    return jsonify({"labels": labels, "datasets": [
        {"label": "Payments",  "data": _vol(1840, dip_at=4, dip_factor=0.55), "color": "#ef4444"},
        {"label": "Transfers", "data": _vol(970),                              "color": "#6366f1"},
        {"label": "ATM",       "data": _vol(820, dip_at=6, dip_factor=0.78),  "color": "#f97316"},
        {"label": "SWIFT",     "data": _vol(57),                               "color": "#22c55e"},
    ]})


@app.route("/api/charts/infrastructure")
def api_chart_infra():
    hosts = [
        {"name": "fraud-ml-node-01",    "cpu": _jitter(94.2, 0.03), "memory": _jitter(87.1, 0.03), "status": "critical"},
        {"name": "core-db-primary-01",  "cpu": _jitter(78.3, 0.03), "memory": _jitter(91.4, 0.03), "status": "warning"},
        {"name": "atm-gateway-02",      "cpu": _jitter(55.1, 0.03), "memory": _jitter(68.2, 0.03), "status": "warning"},
        {"name": "payment-gw-node-01",  "cpu": _jitter(88.4, 0.03), "memory": _jitter(74.5, 0.03), "status": "high"},
        {"name": "core-banking-app-01", "cpu": _jitter(62.1, 0.03), "memory": _jitter(71.8, 0.03), "status": "healthy"},
        {"name": "fraud-api-01",        "cpu": _jitter(41.3, 0.03), "memory": _jitter(55.9, 0.03), "status": "healthy"},
    ]
    return jsonify({"hosts": hosts})


@app.route("/api/charts/trace-waterfall")
def api_trace_waterfall():
    """Distributed trace waterfall for the slowest recent transaction."""
    total_ms = _jitter(3840, 0.05)
    spans = [
        {"name": "POST /v2/payments/transfer", "service": "payment-gateway",           "start_ms": 0,    "duration_ms": _jitter(3840, 0.05), "status": "error",  "color": "#ef4444"},
        {"name": "validate_payment_request",   "service": "payment-gateway",           "start_ms": 2,    "duration_ms": _jitter(12, 0.1),    "status": "ok",     "color": "#22c55e"},
        {"name": "check_fraud_score",          "service": "fraud-detection",           "start_ms": 14,   "duration_ms": _jitter(38, 0.1),    "status": "ok",     "color": "#22c55e"},
        {"name": "debit_account",              "service": "core-banking-api",          "start_ms": 52,   "duration_ms": _jitter(1840, 0.05), "status": "slow",   "color": "#eab308", "issue": "SQL query timeout on ACCOUNTS table"},
        {"name": "POST /api/submit",           "service": "clearing-house-connector",  "start_ms": 1892, "duration_ms": _jitter(1950, 0.05), "status": "error",  "color": "#ef4444", "issue": "ConnectTimeout after 30000ms"},
    ]
    return jsonify({
        "trace_id":        "abc123def456789",
        "transaction_id":  "TXN-98234",
        "total_ms":        round(total_ms),
        "result":          "failure",
        "timestamp":       _now().isoformat(),
        "spans":           spans,
        "root_cause":      "clearing-house-connector timeout (1950ms) + core-banking-api slow DB span (1840ms)",
        "stats": {
            "total_traces":   47,
            "avg_ms":         _jitter(2340),
            "p99_ms":         _jitter(4100),
            "error_rate_pct": _jitter(8.5),
        },
    })


# ---------------------------------------------------------------------------
# API -- New v2 endpoints
# ---------------------------------------------------------------------------

@app.route("/api/analytics/anomalies")
def api_anomalies():
    return jsonify(get_mock_anomaly_report())


@app.route("/api/analytics/correlation")
def api_correlation():
    return jsonify(get_mock_correlation_report())


@app.route("/api/analytics/forecasts")
def api_forecasts():
    return jsonify(get_mock_forecasts())


@app.route("/api/analytics/burn-rates")
def api_burn_rates():
    return jsonify(get_mock_burn_rate_report())


@app.route("/api/memory")
def api_memory():
    return jsonify(get_mock_memory_context())


@app.route("/api/threat-intel")
def api_threat_intel():
    return jsonify(get_mock_threat_summary())


@app.route("/api/pagerduty")
def api_pagerduty():
    return jsonify(get_mock_pagerduty_status())


@app.route("/api/runbooks")
def api_runbooks():
    return jsonify(get_mock_runbook_queue())


@app.route("/api/webhooks/events")
def api_webhook_events():
    return jsonify(get_mock_webhook_events())


@app.route("/api/compliance")
def api_compliance():
    data = json.loads(execute_compliance_tool("compliance_get_pci_scorecard", {}))
    return jsonify(data)


@app.route("/api/cost")
def api_cost():
    anomalies = json.loads(execute_cost_tool("cost_get_anomalies", {"sensitivity": "medium"}))
    budget    = json.loads(execute_cost_tool("cost_get_budget_status", {}))
    return jsonify({"anomalies": anomalies, "budget": budget})


@app.route("/api/environments")
def api_environments():
    """Multi-environment health comparison."""
    return jsonify({
        "environments": [
            {
                "name": "prod",
                "status": "critical",
                "services_degraded": 3,
                "active_alerts": 13,
                "k8s_version": "1.29.4",
                "app_version": "v2.3.4",
                "last_deploy": "2026-04-12T18:30:00Z",
            },
            {
                "name": "staging",
                "status": "warning",
                "services_degraded": 1,
                "active_alerts": 2,
                "k8s_version": "1.29.4",
                "app_version": "v2.3.4",
                "last_deploy": "2026-04-13T10:15:00Z",
                "drift": "LOG_LEVEL=DEBUG set in staging -- matches the prod PCI violation root cause",
            },
            {
                "name": "dr",
                "status": "healthy",
                "services_degraded": 0,
                "active_alerts": 0,
                "k8s_version": "1.28.9",
                "app_version": "v2.3.1",
                "last_deploy": "2026-03-28T09:00:00Z",
                "drift": "K8s version behind (1.28.9 vs prod 1.29.4); app version behind (v2.3.1 vs v2.3.4)",
            },
        ],
    })


@app.route("/api/postmortem")
def api_postmortem():
    return jsonify(get_mock_postmortem())


# ---------------------------------------------------------------------------
# Agent raw data endpoints
# ---------------------------------------------------------------------------

@app.route("/api/dynatrace")
def api_dynatrace():
    problems   = json.loads(execute_dynatrace_tool("dynatrace_get_problems", {"status": "OPEN"}))
    slos       = json.loads(execute_dynatrace_tool("dynatrace_get_slo_status", {}))
    infra      = json.loads(execute_dynatrace_tool("dynatrace_get_infrastructure_health", {}))
    synthetics = json.loads(execute_dynatrace_tool("dynatrace_get_synthetic_monitors", {}))
    databases  = json.loads(execute_dynatrace_tool("dynatrace_get_database_metrics", {}))
    return jsonify({"agent": "Dynatrace", "status": "active", "last_run": _now().isoformat(),
                    "problems": problems, "slos": slos, "infra": infra, "synthetics": synthetics, "databases": databases})


@app.route("/api/azure")
def api_azure():
    alerts   = json.loads(execute_azure_tool("azure_get_active_alerts", {"severity": "ALL", "time_range_hours": 1}))
    svc_hlth = json.loads(execute_azure_tool("azure_get_service_health", {}))
    aks      = json.loads(execute_azure_tool("azure_get_aks_cluster_health", {}))
    security = json.loads(execute_azure_tool("azure_get_security_alerts", {"alert_severity": "High", "time_range_hours": 24}))
    return jsonify({"agent": "Azure Monitor", "status": "active", "last_run": _now().isoformat(),
                    "alerts": alerts, "service_health": svc_hlth, "aks": aks, "security": security})


@app.route("/api/kibana")
def api_kibana():
    errors     = json.loads(execute_kibana_tool("kibana_get_error_rate_aggregation", {"time_range_minutes": 60}))
    sec_events = json.loads(execute_kibana_tool("kibana_get_security_events", {"severity": "high", "time_range_hours": 1}))
    txn        = json.loads(execute_kibana_tool("kibana_get_transaction_analytics", {}))
    rules      = json.loads(execute_kibana_tool("kibana_get_alert_rules_status", {}))
    return jsonify({"agent": "Kibana/ELK", "status": "active", "last_run": _now().isoformat(),
                    "error_rates": errors, "security_events": sec_events, "transactions": txn, "alert_rules": rules})


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    print("Starting Bank IT Operations Dashboard v2...")
    print("Open: http://localhost:5000")
    # Start WebSocket background push thread
    bg = Thread(target=_background_push, daemon=True)
    bg.start()
    socketio.run(app, debug=False, host="0.0.0.0", port=5000, use_reloader=False, allow_unsafe_werkzeug=True)
