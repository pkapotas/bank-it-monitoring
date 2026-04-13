"""
Azure Cost Management Tool Definitions. 6 tools for the Cost agent.
Detects spend anomalies, runaway resources, and budget breaches.
"""
import json
import random
from datetime import datetime, timedelta

COST_TOOLS = [
    {
        "name": "cost_get_daily_spend",
        "description": "Retrieve daily Azure spend for the last N days, broken down by service and resource group.",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "default": 7}, "resource_group": {"type": "string"}}, "required": []},
    },
    {
        "name": "cost_get_anomalies",
        "description": "Detect cost anomalies using Azure Cost Anomaly Detection: resources with unusual spend spikes vs historical baseline.",
        "input_schema": {"type": "object", "properties": {"sensitivity": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"}, "days": {"type": "integer", "default": 7}}, "required": []},
    },
    {
        "name": "cost_get_top_resources",
        "description": "Return the top N most expensive Azure resources by cost in the current billing period.",
        "input_schema": {"type": "object", "properties": {"top_n": {"type": "integer", "default": 10}, "sort_by": {"type": "string", "enum": ["cost", "cost_change_pct"], "default": "cost"}}, "required": []},
    },
    {
        "name": "cost_get_budget_status",
        "description": "Check budget consumption against defined monthly budgets. Returns forecast vs budget for the current period.",
        "input_schema": {"type": "object", "properties": {"budget_scope": {"type": "string", "enum": ["subscription", "resource_group", "all"], "default": "all"}}, "required": []},
    },
    {
        "name": "cost_get_idle_resources",
        "description": "Identify idle or under-utilized Azure resources: stopped VMs, orphaned disks, unused IPs, empty storage accounts.",
        "input_schema": {"type": "object", "properties": {"resource_type": {"type": "string", "enum": ["vm", "disk", "ip", "storage", "all"], "default": "all"}, "idle_days": {"type": "integer", "default": 7}}, "required": []},
    },
    {
        "name": "cost_get_reserved_instance_coverage",
        "description": "Analyse Reserved Instance (RI) and Savings Plan coverage. Identifies on-demand resources that should be converted to reservations for cost savings.",
        "input_schema": {"type": "object", "properties": {"resource_type": {"type": "string", "enum": ["vm", "sql", "aks", "all"], "default": "all"}}, "required": []},
    },
]


def execute_cost_tool(tool_name: str, tool_input: dict) -> str:
    handlers = {
        "cost_get_daily_spend":                _get_daily_spend,
        "cost_get_anomalies":                  _get_anomalies,
        "cost_get_top_resources":              _get_top_resources,
        "cost_get_budget_status":              _get_budget_status,
        "cost_get_idle_resources":             _get_idle_resources,
        "cost_get_reserved_instance_coverage": _get_ri_coverage,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown cost tool: {tool_name}"})
    try:
        return json.dumps(handler(**tool_input), default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _get_daily_spend(days=7, resource_group=None):
    now = datetime.utcnow()
    baseline = 4200
    daily = []
    for i in range(days):
        date = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        spend = baseline * (1 + random.uniform(-0.05, 0.05))
        if i >= days - 2:  # last 2 days have spike
            spend *= 1.28
        daily.append({"date": date, "spend_eur": round(spend, 2)})
    return {
        "currency": "EUR",
        "period_days": days,
        "daily": daily,
        "total": round(sum(d["spend_eur"] for d in daily), 2),
        "avg_daily": round(sum(d["spend_eur"] for d in daily) / len(daily), 2),
        "trend": "increasing",
    }


def _get_anomalies(sensitivity="medium", days=7):
    now = datetime.utcnow()
    return {
        "anomalies": [
            {
                "resource":        "payment-gateway-aks",
                "resource_type":   "AKS Cluster",
                "anomaly_type":    "spend_spike",
                "current_daily_eur": 892,
                "baseline_daily_eur": 412,
                "deviation_pct":   116.5,
                "first_detected":  (now - timedelta(days=1)).isoformat(),
                "probable_cause":  "Node auto-scale triggered by error-loop under degraded clearing-house conditions; 3 extra nodes running 20+ hours",
                "estimated_waste_eur": 480,
                "action":          "Resolve INC-001 (clearing-house timeout) to stop auto-scale; cordon extra nodes",
            },
            {
                "resource":        "fraud-ml-training-job",
                "resource_type":   "Azure Machine Learning Compute",
                "anomaly_type":    "unscheduled_compute",
                "current_daily_eur": 340,
                "baseline_daily_eur": 0,
                "deviation_pct":   100,
                "first_detected":  (now - timedelta(hours=45)).isoformat(),
                "probable_cause":  "ML model re-training job triggered outside scheduled window (should run 03:00-05:00 UTC only)",
                "estimated_waste_eur": 340,
                "action":          "Terminate runaway training job; enforce scheduled trigger only",
            },
            {
                "resource":        "bank-log-analytics-workspace",
                "resource_type":   "Log Analytics",
                "anomaly_type":    "ingestion_spike",
                "current_daily_eur": 218,
                "baseline_daily_eur": 95,
                "deviation_pct":   129.5,
                "first_detected":  (now - timedelta(days=2)).isoformat(),
                "probable_cause":  "payment-gateway DEBUG logging enabled -- verbose request/response bodies increasing ingestion 2.3x",
                "estimated_waste_eur": 123,
                "action":          "Revert payment-gateway log level to INFO; fix root PCI-DSS violation simultaneously",
            },
        ],
        "total_anomalies": 3,
        "estimated_monthly_waste_eur": 28_560,
        "sensitivity": sensitivity,
    }


def _get_top_resources(top_n=10, sort_by="cost"):
    return {
        "period": "current month",
        "currency": "EUR",
        "resources": [
            {"rank": 1, "name": "core-banking-sqlserver",       "type": "Azure SQL (P4)",       "mtd_cost_eur": 18_400, "daily_avg_eur": 613, "mom_change_pct": +8.2},
            {"rank": 2, "name": "payment-gateway-aks",          "type": "AKS Cluster (8 nodes)", "mtd_cost_eur": 12_100, "daily_avg_eur": 403, "mom_change_pct": +28.4, "anomaly": True},
            {"rank": 3, "name": "fraud-detection-aks",          "type": "AKS Cluster (6 nodes)", "mtd_cost_eur": 9_800,  "daily_avg_eur": 327, "mom_change_pct": +12.1},
            {"rank": 4, "name": "bank-log-analytics-workspace", "type": "Log Analytics",         "mtd_cost_eur": 6_540,  "daily_avg_eur": 218, "mom_change_pct": +38.7, "anomaly": True},
            {"rank": 5, "name": "fraud-ml-training-compute",    "type": "AzureML Compute",       "mtd_cost_eur": 5_100,  "daily_avg_eur": 170, "mom_change_pct": +210,  "anomaly": True},
        ][:top_n],
    }


def _get_budget_status(budget_scope="all"):
    return {
        "budgets": [
            {"name": "bank-prod-rg monthly",    "budget_eur": 120_000, "spent_eur": 87_240, "forecast_eur": 128_800, "pct_used": 72.7, "status": "OVER_FORECAST", "days_remaining": 17},
            {"name": "bank-security-rg monthly", "budget_eur": 15_000,  "spent_eur": 10_200, "forecast_eur": 13_800, "pct_used": 68.0, "status": "on_track",      "days_remaining": 17},
            {"name": "bank-dr-rg monthly",        "budget_eur": 20_000,  "spent_eur": 8_400,  "forecast_eur": 14_300, "pct_used": 42.0, "status": "on_track",      "days_remaining": 17},
        ],
        "overall_forecast_eur": 156_900,
        "overall_budget_eur":   155_000,
        "overage_risk_eur":     1_900,
        "status":               "AT_RISK",
    }


def _get_idle_resources(resource_type="all", idle_days=7):
    return {
        "idle_resources": [
            {"name": "atm-gateway-vm-01-snapshot-20260101", "type": "Managed Disk Snapshot", "idle_days": 103, "monthly_cost_eur": 42, "action": "Delete if no longer needed"},
            {"name": "bank-dev-publicip-04",                 "type": "Public IP Address",     "idle_days": 45,  "monthly_cost_eur": 4,  "action": "Release unattached IP"},
            {"name": "legacy-swift-vm-02",                   "type": "Virtual Machine (B2s)", "idle_days": 18,  "monthly_cost_eur": 38, "action": "Stop or deallocate VM"},
            {"name": "bank-test-storage-2025q3",             "type": "Storage Account",       "idle_days": 92,  "monthly_cost_eur": 12, "action": "Archive or delete test data"},
        ],
        "total_idle_resources": 4,
        "monthly_waste_eur":    96,
        "annual_waste_eur":     1_152,
    }


def _get_ri_coverage():
    return {
        "overall_ri_coverage_pct": 54.2,
        "target_coverage_pct":     75.0,
        "savings_opportunities": [
            {"resource": "core-banking-sqlserver", "type": "Azure SQL", "current": "on-demand", "recommended": "3-year Reserved (Pay upfront)", "monthly_savings_eur": 4_100, "annual_savings_eur": 49_200},
            {"resource": "fraud-detection AKS nodes (6)", "type": "VM (D4s_v3)", "current": "on-demand", "recommended": "1-year Reserved", "monthly_savings_eur": 820, "annual_savings_eur": 9_840},
        ],
        "total_annual_savings_opportunity_eur": 59_040,
        "recommendation": "Purchasing recommended reservations would reduce annual Azure spend by EUR 59K (14.2%)",
    }
