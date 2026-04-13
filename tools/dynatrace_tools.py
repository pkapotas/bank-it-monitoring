"""
Dynatrace API tool definitions for the monitoring agent.

Each function simulates a real Dynatrace API call. Replace the mock responses
with actual `requests` calls to your Dynatrace tenant using config.dynatrace.
"""
import json
import random
from datetime import datetime, timedelta
from typing import Any

from config import config


# ---------------------------------------------------------------------------
# Tool definitions (raw JSON schema format for the Anthropic API)
# ---------------------------------------------------------------------------

DYNATRACE_TOOLS = [
    {
        "name": "dynatrace_get_problems",
        "description": (
            "Fetch active and recent problems from Dynatrace. Returns problem IDs, "
            "titles, severity, impacted entities, root causes, and affected services. "
            "Use this as the first step in any Dynatrace health check."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range": {
                    "type": "string",
                    "description": "Time range for problems. Examples: 'now-1h', 'now-24h', 'now-7d'",
                    "default": "now-1h"
                },
                "status": {
                    "type": "string",
                    "enum": ["OPEN", "RESOLVED", "ALL"],
                    "description": "Filter by problem status",
                    "default": "OPEN"
                },
                "severity": {
                    "type": "string",
                    "enum": ["AVAILABILITY", "ERROR", "PERFORMANCE", "RESOURCE_CONTENTION", "ALL"],
                    "description": "Filter by severity category",
                    "default": "ALL"
                }
            },
            "required": []
        }
    },
    {
        "name": "dynatrace_get_service_metrics",
        "description": (
            "Retrieve key performance metrics for a specific banking service from Dynatrace: "
            "response time (p50/p90/p99), throughput (requests/min), error rate (%), "
            "and availability. Essential for SLA monitoring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to query (e.g., 'payment-gateway', 'core-banking-api')"
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range for metrics. Examples: 'now-1h', 'now-6h'",
                    "default": "now-1h"
                }
            },
            "required": ["service_name"]
        }
    },
    {
        "name": "dynatrace_get_infrastructure_health",
        "description": (
            "Get infrastructure health overview from Dynatrace: host CPU/memory utilization, "
            "disk I/O, network traffic, and process group availability. "
            "Covers on-premises and cloud hosts in the banking environment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["HOST", "PROCESS_GROUP", "CONTAINER", "ALL"],
                    "description": "Type of infrastructure entity to check",
                    "default": "ALL"
                },
                "tag_filter": {
                    "type": "string",
                    "description": "Filter by Dynatrace tag (e.g., 'environment:production', 'criticality:high')",
                    "default": "environment:production"
                }
            },
            "required": []
        }
    },
    {
        "name": "dynatrace_get_slo_status",
        "description": (
            "Check Service Level Objective (SLO) compliance status for banking services. "
            "Returns SLO targets, current performance, burn rate, and error budget remaining. "
            "Critical for regulatory and SLA compliance reporting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slo_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of SLO IDs to check. Leave empty to fetch all SLOs."
                }
            },
            "required": []
        }
    },
    {
        "name": "dynatrace_get_synthetic_monitors",
        "description": (
            "Get results from Dynatrace synthetic monitors (browser tests and HTTP checks) "
            "that simulate customer transactions: login, fund transfer, balance check, etc. "
            "Reports availability, step failures, and response times from global locations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "monitor_type": {
                    "type": "string",
                    "enum": ["BROWSER", "HTTP", "ALL"],
                    "description": "Type of synthetic monitor",
                    "default": "ALL"
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range for synthetic results",
                    "default": "now-1h"
                }
            },
            "required": []
        }
    },
    {
        "name": "dynatrace_get_database_metrics",
        "description": (
            "Retrieve database performance metrics from Dynatrace: query execution time, "
            "connection pool usage, slow queries, lock waits, and replication lag. "
            "Covers Oracle, SQL Server, and PostgreSQL instances used by core banking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "database_name": {
                    "type": "string",
                    "description": "Database instance name. Leave empty to check all monitored databases."
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range for database metrics",
                    "default": "now-1h"
                }
            },
            "required": []
        }
    }
]


# ---------------------------------------------------------------------------
# Tool executor -- dispatches tool calls to the correct function
# ---------------------------------------------------------------------------

def execute_dynatrace_tool(tool_name: str, tool_input: dict) -> str:
    """
    Execute a Dynatrace tool call and return a JSON string result.
    Replace mock implementations with real Dynatrace API calls.
    """
    handlers = {
        "dynatrace_get_problems": _get_problems,
        "dynatrace_get_service_metrics": _get_service_metrics,
        "dynatrace_get_infrastructure_health": _get_infrastructure_health,
        "dynatrace_get_slo_status": _get_slo_status,
        "dynatrace_get_synthetic_monitors": _get_synthetic_monitors,
        "dynatrace_get_database_metrics": _get_database_metrics,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown Dynatrace tool: {tool_name}"})
    try:
        result = handler(**tool_input)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Mock implementations -- replace with real Dynatrace API calls
# Real pattern:
#   import requests
#   headers = {"Authorization": f"Api-Token {config.dynatrace.api_token}"}
#   resp = requests.get(f"{config.dynatrace.base_url}/api/v2/problems", headers=headers, params={...})
#   return resp.json()
# ---------------------------------------------------------------------------

def _get_problems(time_range="now-1h", status="OPEN", severity="ALL") -> dict:
    now = datetime.utcnow()
    problems = [
        {
            "problemId": "P-2847",
            "title": "High failure rate on payment-gateway /v2/transfers endpoint",
            "severity": "AVAILABILITY",
            "status": "OPEN",
            "startTime": (now - timedelta(minutes=23)).isoformat(),
            "affectedEntities": ["payment-gateway", "transaction-processor"],
            "rootCause": "Increased connection timeouts to downstream clearing house API",
            "impactLevel": "APPLICATION",
            "impactedUsers": 342,
            "tags": ["environment:production", "criticality:high", "team:payments"],
        },
        {
            "problemId": "P-2851",
            "title": "Response time degradation on core-banking-api",
            "severity": "PERFORMANCE",
            "status": "OPEN",
            "startTime": (now - timedelta(minutes=8)).isoformat(),
            "affectedEntities": ["core-banking-api"],
            "rootCause": "Slow SQL queries detected -- missing index on accounts table",
            "impactLevel": "SERVICE",
            "impactedUsers": 1205,
            "tags": ["environment:production", "criticality:critical", "team:core-banking"],
        },
        {
            "problemId": "P-2839",
            "title": "fraud-detection service CPU saturation",
            "severity": "RESOURCE_CONTENTION",
            "status": "OPEN",
            "startTime": (now - timedelta(minutes=45)).isoformat(),
            "affectedEntities": ["fraud-detection"],
            "rootCause": "ML model re-training job consuming excessive CPU",
            "impactLevel": "INFRASTRUCTURE",
            "impactedUsers": 0,
            "tags": ["environment:production", "criticality:high", "team:fraud"],
        },
    ]
    return {
        "totalCount": len(problems),
        "timeRange": time_range,
        "problems": problems if status in ("OPEN", "ALL") else [],
    }


def _get_service_metrics(service_name: str, time_range="now-1h") -> dict:
    # Simulate different health profiles per service
    profiles = {
        "payment-gateway":       {"error_rate": 4.7, "p50": 245, "p90": 890, "p99": 3200, "throughput": 1840, "availability": 98.2},
        "core-banking-api":      {"error_rate": 0.3, "p50": 420, "p90": 1850, "p99": 4100, "throughput": 3120, "availability": 99.7},
        "fraud-detection":       {"error_rate": 0.1, "p50": 38,  "p90": 95,   "p99": 210,  "throughput": 9800, "availability": 99.9},
        "authentication-service":{"error_rate": 0.05,"p50": 22,  "p90": 65,   "p99": 120,  "throughput": 14300,"availability": 99.99},
        "transaction-processor": {"error_rate": 1.2, "p50": 310, "p90": 720,  "p99": 1800, "throughput": 2450, "availability": 99.4},
        "account-management":    {"error_rate": 0.2, "p50": 180, "p90": 450,  "p99": 980,  "throughput": 5600, "availability": 99.8},
        "swift-connector":       {"error_rate": 0.8, "p50": 520, "p90": 1200, "p99": 2900, "throughput": 340,  "availability": 99.5},
        "atm-network":           {"error_rate": 2.1, "p50": 680, "p90": 1900, "p99": 5200, "throughput": 820,  "availability": 97.8},
    }
    m = profiles.get(service_name, {"error_rate": random.uniform(0.1, 3.0), "p50": random.randint(100, 600), "p90": random.randint(500, 2000), "p99": random.randint(1000, 5000), "throughput": random.randint(100, 5000), "availability": round(random.uniform(97.0, 99.99), 2)})
    return {
        "serviceName": service_name,
        "timeRange": time_range,
        "metrics": {
            "errorRate": {"value": m["error_rate"], "unit": "%", "trend": "increasing" if m["error_rate"] > 2 else "stable"},
            "responseTime": {"p50_ms": m["p50"], "p90_ms": m["p90"], "p99_ms": m["p99"], "trend": "degrading" if m["p90"] > 1000 else "stable"},
            "throughput": {"requestsPerMin": m["throughput"], "trend": "stable"},
            "availability": {"value": m["availability"], "unit": "%"},
        },
        "slaBreaches": [
            f"p99 response time {m['p99']}ms exceeds 3000ms SLA" if m["p99"] > 3000 else None,
            f"Error rate {m['error_rate']}% exceeds 2% warning threshold" if m["error_rate"] > 2.0 else None,
        ],
    }


def _get_infrastructure_health(entity_type="ALL", tag_filter="environment:production") -> dict:
    return {
        "tagFilter": tag_filter,
        "summary": {
            "totalHosts": 48,
            "hostsWithProblems": 3,
            "avgCpuUtilization": 62.4,
            "avgMemoryUtilization": 71.8,
        },
        "criticalHosts": [
            {"hostId": "HOST-A3F9", "name": "fraud-ml-node-01", "cpu": 94.2, "memory": 87.1, "issue": "CPU saturation -- ML training job"},
            {"hostId": "HOST-B7D2", "name": "core-db-primary-01", "cpu": 78.3, "memory": 91.4, "issue": "High memory pressure -- buffer pool at limit"},
            {"hostId": "HOST-C1E8", "name": "atm-gateway-02", "cpu": 55.1, "memory": 68.2, "issue": "Disk I/O saturation -- 98% utilization"},
        ],
        "processGroups": {
            "total": 156,
            "unhealthy": 4,
            "unhealthyList": ["oracle-core-banking", "redis-session-cache", "nginx-api-gateway", "kafka-transaction-bus"],
        },
    }


def _get_slo_status(slo_ids=None) -> dict:
    return {
        "slos": [
            {"id": "SLO-001", "name": "Payment Gateway Availability", "target": 99.9, "current": 98.2, "errorBudgetRemaining": -0.7, "status": "VIOLATED", "burnRate": 3.2},
            {"id": "SLO-002", "name": "Core Banking API Response Time p95 < 2s", "target": 95.0, "current": 91.3, "errorBudgetRemaining": 12.4, "status": "WARNING", "burnRate": 1.8},
            {"id": "SLO-003", "name": "Authentication Service Availability", "target": 99.99, "current": 99.99, "errorBudgetRemaining": 98.5, "status": "OK", "burnRate": 0.02},
            {"id": "SLO-004", "name": "Fraud Detection Latency p99 < 500ms", "target": 99.0, "current": 99.7, "errorBudgetRemaining": 87.3, "status": "OK", "burnRate": 0.3},
            {"id": "SLO-005", "name": "ATM Network Availability", "target": 99.5, "current": 97.8, "errorBudgetRemaining": -1.4, "status": "VIOLATED", "burnRate": 4.1},
        ],
        "summary": {"total": 5, "ok": 2, "warning": 1, "violated": 2},
    }


def _get_synthetic_monitors(monitor_type="ALL", time_range="now-1h") -> dict:
    return {
        "monitors": [
            {"id": "SM-001", "name": "Customer Login Flow", "type": "BROWSER", "availability": 97.8, "avgDuration_ms": 2340, "failedChecks": 3, "locations": ["Frankfurt", "London", "New York"], "lastFailureReason": "Step 3 (2FA verification) timeout after 10s"},
            {"id": "SM-002", "name": "Fund Transfer End-to-End", "type": "BROWSER", "availability": 96.1, "avgDuration_ms": 4820, "failedChecks": 7, "locations": ["Frankfurt", "Singapore"], "lastFailureReason": "HTTP 503 from payment-gateway"},
            {"id": "SM-003", "name": "Balance Check API", "type": "HTTP", "availability": 99.9, "avgDuration_ms": 185, "failedChecks": 0, "locations": ["Frankfurt"], "lastFailureReason": None},
            {"id": "SM-004", "name": "SWIFT MT103 Submission", "type": "HTTP", "availability": 99.2, "avgDuration_ms": 1240, "failedChecks": 1, "locations": ["Frankfurt", "London"], "lastFailureReason": "Response time exceeded 3000ms threshold"},
        ],
        "summary": {"total": 4, "passing": 2, "failing": 2},
    }


def _get_database_metrics(database_name=None, time_range="now-1h") -> dict:
    return {
        "databases": [
            {"name": "ORACLE-CORE-BANKING", "type": "Oracle 19c", "status": "degraded", "avgQueryTime_ms": 1840, "slowQueries": 23, "connectionPoolUsage": 87, "lockWaits": 145, "replicationLag_ms": 0, "issue": "Missing index causing full table scans on ACCOUNTS table"},
            {"name": "SQLSERVER-FRAUD-DB",  "type": "SQL Server 2022", "status": "healthy", "avgQueryTime_ms": 42, "slowQueries": 1, "connectionPoolUsage": 34, "lockWaits": 3, "replicationLag_ms": 12, "issue": None},
            {"name": "POSTGRES-AUDIT-LOG",  "type": "PostgreSQL 15", "status": "healthy", "avgQueryTime_ms": 28, "slowQueries": 0, "connectionPoolUsage": 22, "lockWaits": 0, "replicationLag_ms": 45, "issue": None},
            {"name": "REDIS-SESSION",        "type": "Redis 7.2", "status": "warning", "avgQueryTime_ms": 4, "slowQueries": 0, "connectionPoolUsage": 91, "lockWaits": 0, "replicationLag_ms": 0, "issue": "Connection pool near capacity -- 91% utilized"},
        ],
        "summary": {"total": 4, "healthy": 2, "warning": 1, "degraded": 1},
    }
