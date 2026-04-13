"""
Bank IT Operations - Real-Time Monitoring Dashboard
Flask backend that exposes all mock monitoring data as JSON APIs.
Run:  python dashboard/app.py
Then open: http://localhost:5000
"""
import json
import math
import random
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, render_template, send_from_directory
from tools.dynatrace_tools import execute_dynatrace_tool
from tools.azure_tools import execute_azure_tool
from tools.kibana_tools import execute_kibana_tool

app = Flask(__name__, template_folder="templates", static_folder="static")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jitter(base, pct=0.08):
    """Add small random jitter to a float so charts look live."""
    return round(base * (1 + random.uniform(-pct, pct)), 2)


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# API — Agent status snapshots
# ---------------------------------------------------------------------------

@app.route("/api/dynatrace")
def api_dynatrace():
    problems   = json.loads(execute_dynatrace_tool("dynatrace_get_problems", {"status": "OPEN"}))
    slos       = json.loads(execute_dynatrace_tool("dynatrace_get_slo_status", {}))
    infra      = json.loads(execute_dynatrace_tool("dynatrace_get_infrastructure_health", {}))
    synthetics = json.loads(execute_dynatrace_tool("dynatrace_get_synthetic_monitors", {}))
    databases  = json.loads(execute_dynatrace_tool("dynatrace_get_database_metrics", {}))
    return jsonify({
        "agent": "Dynatrace",
        "status": "active",
        "last_run": _now().isoformat(),
        "problems": problems,
        "slos": slos,
        "infra": infra,
        "synthetics": synthetics,
        "databases": databases,
    })


@app.route("/api/azure")
def api_azure():
    alerts   = json.loads(execute_azure_tool("azure_get_active_alerts", {"severity": "ALL", "time_range_hours": 1}))
    svc_hlth = json.loads(execute_azure_tool("azure_get_service_health", {}))
    aks      = json.loads(execute_azure_tool("azure_get_aks_cluster_health", {}))
    security = json.loads(execute_azure_tool("azure_get_security_alerts", {"alert_severity": "High", "time_range_hours": 24}))
    return jsonify({
        "agent": "Azure Monitor",
        "status": "active",
        "last_run": _now().isoformat(),
        "alerts": alerts,
        "service_health": svc_hlth,
        "aks": aks,
        "security": security,
    })


@app.route("/api/kibana")
def api_kibana():
    errors      = json.loads(execute_kibana_tool("kibana_get_error_rate_aggregation", {"time_range_minutes": 60}))
    sec_events  = json.loads(execute_kibana_tool("kibana_get_security_events", {"severity": "high", "time_range_hours": 1}))
    txn         = json.loads(execute_kibana_tool("kibana_get_transaction_analytics", {}))
    rules       = json.loads(execute_kibana_tool("kibana_get_alert_rules_status", {}))
    return jsonify({
        "agent": "Kibana/ELK",
        "status": "active",
        "last_run": _now().isoformat(),
        "error_rates": errors,
        "security_events": sec_events,
        "transactions": txn,
        "alert_rules": rules,
    })


# ---------------------------------------------------------------------------
# API — Service health grid (combined across all sources)
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


# ---------------------------------------------------------------------------
# API — Time-series chart data (simulated history for the last 60 minutes)
# ---------------------------------------------------------------------------

@app.route("/api/charts/error-rates")
def api_chart_error_rates():
    """60-minute error rate history for top services, sampled every 5 minutes."""
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

    return jsonify({
        "labels": labels,
        "datasets": [
            {"label": "payment-gateway",   "data": _series(0.5, spike_at=4, spike_val=4.7),  "color": "#ef4444"},
            {"label": "atm-network",       "data": _series(0.8, spike_at=6, spike_val=2.1),  "color": "#f97316"},
            {"label": "txn-processor",     "data": _series(0.3, spike_at=7, spike_val=1.2),  "color": "#eab308"},
            {"label": "core-banking-api",  "data": _series(0.3),                             "color": "#6366f1"},
            {"label": "fraud-detection",   "data": _series(0.1),                             "color": "#22c55e"},
        ]
    })


@app.route("/api/charts/response-times")
def api_chart_response_times():
    """Current p50/p90/p99 response times per service."""
    services = [
        {"service": "payment-gateway",   "p50": _jitter(245),  "p90": _jitter(890),  "p99": _jitter(3200)},
        {"service": "core-banking-api",   "p50": _jitter(420),  "p90": _jitter(1850), "p99": _jitter(4100)},
        {"service": "txn-processor",      "p50": _jitter(310),  "p90": _jitter(720),  "p99": _jitter(1800)},
        {"service": "swift-connector",    "p50": _jitter(520),  "p90": _jitter(1200), "p99": _jitter(2900)},
        {"service": "atm-network",        "p50": _jitter(680),  "p90": _jitter(1900), "p99": _jitter(5200)},
        {"service": "account-mgmt",       "p50": _jitter(180),  "p90": _jitter(450),  "p99": _jitter(980)},
        {"service": "fraud-detection",    "p50": _jitter(38),   "p90": _jitter(95),   "p99": _jitter(210)},
        {"service": "auth-service",       "p50": _jitter(22),   "p90": _jitter(65),   "p99": _jitter(120)},
    ]
    return jsonify({"services": services})


@app.route("/api/charts/transaction-volume")
def api_chart_txn_volume():
    """Transaction volumes over the last 60 minutes by type."""
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

    return jsonify({
        "labels": labels,
        "datasets": [
            {"label": "Payments",  "data": _vol(1840, dip_at=4, dip_factor=0.55), "color": "#ef4444"},
            {"label": "Transfers", "data": _vol(970),                              "color": "#6366f1"},
            {"label": "ATM",       "data": _vol(820,  dip_at=6, dip_factor=0.78), "color": "#f97316"},
            {"label": "SWIFT",     "data": _vol(57),                               "color": "#22c55e"},
        ]
    })


@app.route("/api/charts/infrastructure")
def api_chart_infra():
    """Infrastructure resource utilization."""
    hosts = [
        {"name": "fraud-ml-node-01",   "cpu": _jitter(94.2, 0.03), "memory": _jitter(87.1, 0.03), "status": "critical"},
        {"name": "core-db-primary-01", "cpu": _jitter(78.3, 0.03), "memory": _jitter(91.4, 0.03), "status": "warning"},
        {"name": "atm-gateway-02",     "cpu": _jitter(55.1, 0.03), "memory": _jitter(68.2, 0.03), "status": "warning"},
        {"name": "payment-gw-node-01", "cpu": _jitter(88.4, 0.03), "memory": _jitter(74.5, 0.03), "status": "high"},
        {"name": "core-banking-app-01","cpu": _jitter(62.1, 0.03), "memory": _jitter(71.8, 0.03), "status": "healthy"},
        {"name": "fraud-api-01",       "cpu": _jitter(41.3, 0.03), "memory": _jitter(55.9, 0.03), "status": "healthy"},
    ]
    return jsonify({"hosts": hosts})


# ---------------------------------------------------------------------------
# API — Consolidated alert feed
# ---------------------------------------------------------------------------

@app.route("/api/alerts")
def api_alerts():
    now = _now()
    alerts = [
        # Dynatrace problems
        {"id": "DT-P2847",   "source": "Dynatrace", "severity": "critical", "category": "availability",  "title": "High failure rate on payment-gateway /v2/transfers",      "service": "payment-gateway",        "age_min": 23, "correlated": ["AZ-003", "KB-TXN"]},
        {"id": "DT-P2851",   "source": "Dynatrace", "severity": "high",     "category": "performance",   "title": "Response time degradation on core-banking-api",           "service": "core-banking-api",       "age_min": 8,  "correlated": ["AZ-002", "KB-APM"]},
        {"id": "DT-P2839",   "source": "Dynatrace", "severity": "high",     "category": "resource",      "title": "fraud-detection service CPU saturation (94%)",            "service": "fraud-detection",        "age_min": 45, "correlated": []},
        # Azure alerts
        {"id": "AZ-001",     "source": "Azure",     "severity": "high",     "category": "compute",       "title": "AKS node NotReady + pod CrashLoopBackOff (OOMKilled)",   "service": "payment-gateway-aks",    "age_min": 18, "correlated": ["DT-P2847"]},
        {"id": "AZ-002",     "source": "Azure",     "severity": "high",     "category": "database",      "title": "Azure SQL DTU approaching limit (87%) -- core-banking-db","service": "core-banking-sqlserver", "age_min": 31, "correlated": ["DT-P2851"]},
        {"id": "AZ-003",     "source": "Azure",     "severity": "warning",  "category": "messaging",     "title": "Service Bus DLQ growing: 847 messages in transaction-events","service": "bank-servicebus",      "age_min": 12, "correlated": ["DT-P2847"]},
        {"id": "AZ-SEC1",    "source": "Azure",     "severity": "critical", "category": "security",      "title": "Brute force attack on Azure SQL -- 185.220.101.47",        "service": "core-banking-sqlserver", "age_min": 120,"correlated": ["KB-SEC1"]},
        {"id": "AZ-SEC2",    "source": "Azure",     "severity": "critical", "category": "security",      "title": "Suspicious PowerShell execution on atm-gateway-vm-02",    "service": "atm-network",            "age_min": 300,"correlated": []},
        # Kibana / SIEM
        {"id": "KB-SEC1",    "source": "Kibana",    "severity": "critical", "category": "security",      "title": "Credential stuffing: 87 failed logins from Tor exit node", "service": "authentication-service", "age_min": 42, "correlated": ["AZ-SEC1"]},
        {"id": "KB-PCI",     "source": "Kibana",    "severity": "critical", "category": "compliance",    "title": "PCI-DSS VIOLATION: PAN detected in payment-gateway debug log","service": "payment-gateway",       "age_min": 8,  "correlated": []},
        {"id": "KB-SEC2",    "source": "Kibana",    "severity": "high",     "category": "security",      "title": "svc-batch-processor accessed 1,240 PII records outside schedule","service": "account-management", "age_min": 15, "correlated": []},
        {"id": "KB-TXN",     "source": "Kibana",    "severity": "high",     "category": "transactions",  "title": "Payment failure rate 4.7% (15x baseline, EUR 24.5M at risk)","service": "payment-gateway",      "age_min": 23, "correlated": ["DT-P2847"]},
        {"id": "KB-APM",     "source": "Kibana",    "severity": "warning",  "category": "performance",   "title": "APM: payment-gateway p99 = 4100ms, error rate 8.5%",       "service": "payment-gateway",        "age_min": 5,  "correlated": ["DT-P2847"]},
    ]
    counts = {
        "critical": sum(1 for a in alerts if a["severity"] == "critical"),
        "high":     sum(1 for a in alerts if a["severity"] == "high"),
        "warning":  sum(1 for a in alerts if a["severity"] == "warning"),
        "total":    len(alerts),
    }
    return jsonify({"alerts": alerts, "counts": counts})


# ---------------------------------------------------------------------------
# API — Orchestrator incident summary
# ---------------------------------------------------------------------------

@app.route("/api/orchestrator")
def api_orchestrator():
    return jsonify({
        "overall_status": "critical",
        "escalation_required": True,
        "generated_at": _now().isoformat(),
        "incident_count": 6,
        "slo_violations": 2,
        "security_events": 3,
        "incidents": [
            {"rank": 1, "id": "INC-001", "severity": "critical", "title": "Payment Gateway Degradation",
             "root_cause": "Clearing-house API timeout (30s) -- CircuitBreaker OPEN",
             "impact": "4.7% failure rate, EUR 24.5M at risk, 342 customers affected/hr",
             "sources": ["Dynatrace", "Azure", "Kibana"], "owner": "Payments Engineering"},
            {"rank": 2, "id": "INC-002", "severity": "critical", "title": "PCI-DSS Compliance Violation",
             "root_cause": "PAN in payment-gateway debug log (PCI-DSS Req 3.3)",
             "impact": "Mandatory 72h notification to card schemes required",
             "sources": ["Kibana"], "owner": "Security & Compliance"},
            {"rank": 3, "id": "INC-003", "severity": "critical", "title": "Active Credential Stuffing Attack",
             "root_cause": "87 login attempts from Tor exit node 185.220.101.47",
             "impact": "Account takeover risk for targeted customers",
             "sources": ["Azure", "Kibana"], "owner": "SOC"},
            {"rank": 4, "id": "INC-004", "severity": "high",     "title": "Core Banking Database Degradation",
             "root_cause": "Missing index on ACCOUNTS table -- full table scans, 1840ms avg",
             "impact": "1,205 users experiencing slow core-banking responses",
             "sources": ["Dynatrace", "Azure"], "owner": "DBA + Core Banking"},
            {"rank": 5, "id": "INC-005", "severity": "high",     "title": "AKS Node Failure (payment cluster)",
             "root_cause": "payment-gw-node-04 NotReady, pod OOMKilled (CrashLoopBackOff)",
             "impact": "Reduced payment-gateway capacity, amplifies INC-001",
             "sources": ["Azure"], "owner": "Platform / SRE"},
            {"rank": 6, "id": "INC-006", "severity": "medium",   "title": "ATM Network Degradation",
             "root_cause": "atm-gateway-02 disk I/O at 98%, SLO-005 violated",
             "impact": "2.1% ATM failure rate, 172 failed transactions/hr",
             "sources": ["Dynatrace", "Kibana"], "owner": "ATM Operations"},
        ],
        "immediate_actions": [
            {"priority": 1, "team": "Payments Eng",     "urgency": "NOW",    "action": "Investigate clearing-house API; consider failover to secondary provider"},
            {"priority": 2, "team": "Security",         "urgency": "NOW",    "action": "Remove PAN from debug logs; file PCI-DSS incident report within 1 hour"},
            {"priority": 3, "team": "SOC",              "urgency": "NOW",    "action": "Block 185.220.101.47 at WAF/NSG; enable step-up MFA for targeted accounts"},
            {"priority": 4, "team": "DBA",              "urgency": "15min",  "action": "Add missing index on ACCOUNTS table; flush Oracle connection pool"},
            {"priority": 5, "team": "SRE",              "urgency": "15min",  "action": "Drain payment-gw-node-04; increase AKS pod memory limits"},
            {"priority": 6, "team": "SOC",              "urgency": "30min",  "action": "Isolate atm-gateway-vm-02; begin forensic investigation"},
        ]
    })


# ---------------------------------------------------------------------------
# API — SLO status
# ---------------------------------------------------------------------------

@app.route("/api/slos")
def api_slos():
    slos = [
        {"id": "SLO-001", "name": "Payment Gateway Availability", "target": 99.9,  "current": _jitter(98.2, 0.005), "budget_pct": _jitter(-0.7, 0.1),  "status": "violated",  "burn_rate": _jitter(3.2)},
        {"id": "SLO-002", "name": "Core Banking p95 < 2s",         "target": 95.0,  "current": _jitter(91.3, 0.005), "budget_pct": _jitter(12.4, 0.1), "status": "warning",   "burn_rate": _jitter(1.8)},
        {"id": "SLO-003", "name": "Auth Service Availability",      "target": 99.99, "current": _jitter(99.99,0.001), "budget_pct": _jitter(98.5, 0.1), "status": "ok",        "burn_rate": _jitter(0.02)},
        {"id": "SLO-004", "name": "Fraud Detection p99 < 500ms",    "target": 99.0,  "current": _jitter(99.7, 0.005), "budget_pct": _jitter(87.3, 0.1), "status": "ok",        "burn_rate": _jitter(0.3)},
        {"id": "SLO-005", "name": "ATM Network Availability",        "target": 99.5,  "current": _jitter(97.8, 0.005), "budget_pct": _jitter(-1.4, 0.1),  "status": "violated",  "burn_rate": _jitter(4.1)},
    ]
    return jsonify({"slos": slos})


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    print("Starting Bank IT Operations Dashboard...")
    print("Open: http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)
