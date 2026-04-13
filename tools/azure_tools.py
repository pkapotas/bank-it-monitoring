"""
Azure Monitor API tool definitions for the monitoring agent.

Replace mock implementations with real Azure SDK calls:
  from azure.identity import ClientSecretCredential
  from azure.mgmt.monitor import MonitorManagementClient
  from azure.monitor.query import LogsQueryClient, MetricsQueryClient
"""
import json
from datetime import datetime, timedelta

from config import config


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

AZURE_TOOLS = [
    {
        "name": "azure_get_active_alerts",
        "description": (
            "Retrieve active Azure Monitor alerts across the banking infrastructure. "
            "Returns alert name, severity (Sev0-Sev4), affected resource, condition, "
            "fired time, and monitor condition. Covers metric, log, and activity log alerts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["Sev0", "Sev1", "Sev2", "Sev3", "Sev4", "ALL"],
                    "description": "Filter by alert severity. Sev0=Critical, Sev1=Error, Sev2=Warning",
                    "default": "ALL"
                },
                "resource_group": {
                    "type": "string",
                    "description": "Azure resource group to scope the query. Defaults to production resource group."
                },
                "time_range_hours": {
                    "type": "integer",
                    "description": "How many hours back to look for alerts",
                    "default": 1
                }
            },
            "required": []
        }
    },
    {
        "name": "azure_get_resource_metrics",
        "description": (
            "Query Azure Monitor metrics for a specific Azure resource: "
            "VMs (CPU, memory, disk, network), App Services (requests, response time, HTTP errors), "
            "Azure SQL (DTU, connections, deadlocks), Azure Kubernetes Service (pod status, node pressure). "
            "Use for deep-dive diagnostics on a specific resource."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "Full Azure resource ID or short name (e.g., 'payment-gateway-vm', 'core-banking-aks')"
                },
                "resource_type": {
                    "type": "string",
                    "enum": ["VirtualMachine", "AppService", "AzureSQL", "AKS", "CosmosDB", "ServiceBus", "APIManagement"],
                    "description": "Type of Azure resource"
                },
                "time_range_hours": {
                    "type": "integer",
                    "description": "Metric time range in hours",
                    "default": 1
                }
            },
            "required": ["resource_id", "resource_type"]
        }
    },
    {
        "name": "azure_query_logs",
        "description": (
            "Execute a KQL (Kusto Query Language) query against the Azure Log Analytics workspace "
            "to search application logs, security events, audit trails, and diagnostic data. "
            "Use for root cause analysis, security investigations, and compliance audits."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kql_query": {
                    "type": "string",
                    "description": "KQL query to execute against the Log Analytics workspace"
                },
                "time_range_hours": {
                    "type": "integer",
                    "description": "Time range for the log query in hours",
                    "default": 1
                }
            },
            "required": ["kql_query"]
        }
    },
    {
        "name": "azure_get_aks_cluster_health",
        "description": (
            "Get health status of Azure Kubernetes Service (AKS) clusters hosting banking microservices. "
            "Returns node status, pod health, resource utilization, failed deployments, "
            "and pending pods for each cluster namespace."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cluster_name": {
                    "type": "string",
                    "description": "AKS cluster name. Leave empty to check all clusters."
                }
            },
            "required": []
        }
    },
    {
        "name": "azure_get_security_alerts",
        "description": (
            "Retrieve Microsoft Defender for Cloud security alerts and recommendations "
            "for the banking Azure environment. Returns threat detections, vulnerability assessments, "
            "suspicious activity alerts, and compliance violations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "alert_severity": {
                    "type": "string",
                    "enum": ["High", "Medium", "Low", "ALL"],
                    "description": "Filter by Defender alert severity",
                    "default": "High"
                },
                "time_range_hours": {
                    "type": "integer",
                    "description": "How many hours back to retrieve security alerts",
                    "default": 24
                }
            },
            "required": []
        }
    },
    {
        "name": "azure_get_service_health",
        "description": (
            "Check Azure Service Health for any platform-level incidents, planned maintenance, "
            "or service advisories affecting regions and services used by the bank "
            "(e.g., West Europe, North Europe -- Azure SQL, AKS, Service Bus, API Management)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "regions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Azure regions to check. Defaults to all regions used by the bank.",
                    "default": ["westeurope", "northeurope", "eastus"]
                }
            },
            "required": []
        }
    }
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def execute_azure_tool(tool_name: str, tool_input: dict) -> str:
    """Execute an Azure Monitor tool call and return a JSON string result."""
    handlers = {
        "azure_get_active_alerts": _get_active_alerts,
        "azure_get_resource_metrics": _get_resource_metrics,
        "azure_query_logs": _query_logs,
        "azure_get_aks_cluster_health": _get_aks_cluster_health,
        "azure_get_security_alerts": _get_security_alerts,
        "azure_get_service_health": _get_service_health,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown Azure tool: {tool_name}"})
    try:
        result = handler(**tool_input)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Mock implementations
# ---------------------------------------------------------------------------

def _get_active_alerts(severity="ALL", resource_group=None, time_range_hours=1) -> dict:
    now = datetime.utcnow()
    rg = resource_group or config.azure.resource_group
    alerts = [
        {
            "alertId": "/subscriptions/.../alerts/alert-001",
            "name": "High CPU on payment-gateway-aks-node-pool",
            "severity": "Sev1",
            "resourceGroup": rg,
            "affectedResource": "payment-gateway-aks/agentpool",
            "condition": "CPU percentage > 90% for 5 minutes",
            "firedTime": (now - timedelta(minutes=18)).isoformat(),
            "monitorCondition": "Fired",
            "description": "Node pool CPU has been above 90% threshold for over 5 minutes",
        },
        {
            "alertId": "/subscriptions/.../alerts/alert-002",
            "name": "Azure SQL DTU limit approaching -- core-banking-db",
            "severity": "Sev1",
            "resourceGroup": rg,
            "affectedResource": "core-banking-sqlserver/core-banking-db",
            "condition": "DTU consumption > 85% for 10 minutes",
            "firedTime": (now - timedelta(minutes=31)).isoformat(),
            "monitorCondition": "Fired",
            "description": "Core banking database approaching DTU limit. Risk of throttling.",
        },
        {
            "alertId": "/subscriptions/.../alerts/alert-003",
            "name": "Service Bus dead-letter queue growing -- transaction-events",
            "severity": "Sev2",
            "resourceGroup": rg,
            "affectedResource": "bank-servicebus/transaction-events",
            "condition": "Dead-letter message count > 500",
            "firedTime": (now - timedelta(minutes=12)).isoformat(),
            "monitorCondition": "Fired",
            "description": "Dead-letter queue has 847 messages. Likely consumer processing failures.",
        },
        {
            "alertId": "/subscriptions/.../alerts/alert-004",
            "name": "API Management gateway errors elevated",
            "severity": "Sev1",
            "resourceGroup": rg,
            "affectedResource": "bank-apim",
            "condition": "Failed requests > 5% of total in 5-minute window",
            "firedTime": (now - timedelta(minutes=22)).isoformat(),
            "monitorCondition": "Fired",
            "description": "6.2% of API requests returning 5xx errors in the last 5 minutes.",
        },
    ]
    return {
        "resourceGroup": rg,
        "timeRangeHours": time_range_hours,
        "totalAlerts": len(alerts),
        "summary": {"Sev0": 0, "Sev1": 3, "Sev2": 1, "Sev3": 0, "Sev4": 0},
        "alerts": alerts,
    }


def _get_resource_metrics(resource_id: str, resource_type: str, time_range_hours=1) -> dict:
    profiles = {
        "payment-gateway-aks": {
            "nodeCount": 6, "cpuPercent": 91.4, "memoryPercent": 74.2,
            "podsPending": 2, "podsRunning": 38, "podsFailed": 1,
        },
        "core-banking-aks": {
            "nodeCount": 12, "cpuPercent": 68.7, "memoryPercent": 82.1,
            "podsPending": 0, "podsRunning": 96, "podsFailed": 0,
        },
    }
    p = profiles.get(resource_id, {"nodeCount": 4, "cpuPercent": 45.0, "memoryPercent": 58.0, "podsPending": 0, "podsRunning": 24, "podsFailed": 0})
    return {
        "resourceId": resource_id,
        "resourceType": resource_type,
        "timeRangeHours": time_range_hours,
        "metrics": p,
        "status": "degraded" if p.get("cpuPercent", 0) > 85 or p.get("podsFailed", 0) > 0 else "healthy",
    }


def _query_logs(kql_query: str, time_range_hours=1) -> dict:
    # Detect query intent from keywords for realistic mocks
    query_lower = kql_query.lower()
    if "error" in query_lower or "exception" in query_lower:
        rows = [
            {"TimeGenerated": "2026-04-13T09:45:12Z", "Level": "Error", "Message": "PaymentProcessor: Connection timeout to clearing house API after 30s", "ServiceName": "payment-gateway", "Count": 47},
            {"TimeGenerated": "2026-04-13T09:52:33Z", "Level": "Error", "Message": "CoreBanking: SQL query exceeded 10s timeout -- SELECT on ACCOUNTS table", "ServiceName": "core-banking-api", "Count": 23},
            {"TimeGenerated": "2026-04-13T09:58:01Z", "Level": "Error", "Message": "SWIFT: MT103 message rejected by partner bank -- invalid BIC code", "ServiceName": "swift-connector", "Count": 3},
        ]
    elif "security" in query_lower or "signin" in query_lower or "failed" in query_lower:
        rows = [
            {"TimeGenerated": "2026-04-13T09:10:44Z", "Level": "Warning", "Message": "Multiple failed login attempts from IP 185.220.101.x -- 45 attempts in 5 minutes", "ServiceName": "authentication-service", "Count": 45},
            {"TimeGenerated": "2026-04-13T09:32:11Z", "Level": "Warning", "Message": "Privileged account access outside business hours -- admin@bank.internal", "ServiceName": "azure-ad", "Count": 1},
        ]
    else:
        rows = [
            {"TimeGenerated": "2026-04-13T09:00:00Z", "Level": "Info", "Message": "Query returned general log results", "Count": 100},
        ]
    return {
        "query": kql_query,
        "timeRangeHours": time_range_hours,
        "rowCount": len(rows),
        "rows": rows,
        "workspaceId": config.azure.log_workspace_id or "workspace-mock-id",
    }


def _get_aks_cluster_health(cluster_name=None) -> dict:
    return {
        "clusters": [
            {
                "name": "payment-gateway-aks",
                "region": "westeurope",
                "kubernetesVersion": "1.29.2",
                "nodePoolStatus": "degraded",
                "nodes": {"total": 6, "ready": 5, "notReady": 1, "cordoned": 0},
                "pods": {"running": 38, "pending": 2, "failed": 1, "total": 41},
                "namespaces": {
                    "payments": {"status": "degraded", "podsFailed": 1},
                    "monitoring": {"status": "healthy", "podsFailed": 0},
                },
                "recentEvents": [
                    "Node payment-gw-node-04 NotReady -- kubelet stopped posting status",
                    "Pod payment-processor-7d4b-xzp9q in CrashLoopBackOff -- OOMKilled",
                ],
            },
            {
                "name": "core-banking-aks",
                "region": "westeurope",
                "kubernetesVersion": "1.29.2",
                "nodePoolStatus": "healthy",
                "nodes": {"total": 12, "ready": 12, "notReady": 0, "cordoned": 0},
                "pods": {"running": 96, "pending": 0, "failed": 0, "total": 96},
                "recentEvents": [],
            },
        ],
        "summary": {"totalClusters": 2, "healthy": 1, "degraded": 1, "down": 0},
    }


def _get_security_alerts(alert_severity="High", time_range_hours=24) -> dict:
    now = datetime.utcnow()
    return {
        "securityAlerts": [
            {
                "id": "sec-alert-001",
                "displayName": "Brute force attack on Azure SQL Server",
                "severity": "High",
                "status": "Active",
                "detectedTime": (now - timedelta(hours=2)).isoformat(),
                "affectedResource": "core-banking-sqlserver",
                "description": "Multiple failed login attempts detected from external IP range 185.220.101.0/24. Possible credential stuffing attack.",
                "remediationSteps": ["Block source IP range in NSG", "Enable SQL Advanced Threat Protection", "Review SQL audit logs"],
            },
            {
                "id": "sec-alert-002",
                "displayName": "Suspicious process execution on VM",
                "severity": "High",
                "status": "Active",
                "detectedTime": (now - timedelta(hours=5)).isoformat(),
                "affectedResource": "atm-gateway-vm-02",
                "description": "Unexpected process 'powershell.exe -EncodedCommand' executed on ATM gateway VM outside maintenance window.",
                "remediationSteps": ["Isolate VM", "Collect forensic evidence", "Escalate to SOC"],
            },
        ],
        "summary": {"high": 2, "medium": 3, "low": 5, "total": 10},
        "secureScore": 67.4,
        "secureScoreTrend": "decreasing",
    }


def _get_service_health(regions=None) -> dict:
    regions = regions or ["westeurope", "northeurope", "eastus"]
    return {
        "incidents": [
            {
                "id": "AZU-2024-0412",
                "title": "Azure Service Bus -- Intermittent connectivity issues",
                "status": "Active",
                "severity": "2 -- Moderate",
                "impactedRegions": ["westeurope"],
                "impactedServices": ["Service Bus"],
                "startTime": "2026-04-13T06:15:00Z",
                "lastUpdate": "2026-04-13T09:30:00Z",
                "summary": "Some customers may experience intermittent connectivity issues with Service Bus namespaces in West Europe. Engineers are actively investigating.",
            }
        ],
        "plannedMaintenance": [],
        "healthAdvisories": [
            {
                "id": "ADV-2024-0410",
                "title": "Azure SQL -- Deprecation of TLS 1.0/1.1",
                "impactedServices": ["Azure SQL Database"],
                "status": "Active",
                "actionRequired": True,
                "deadline": "2026-07-31",
            }
        ],
        "regionsChecked": regions,
        "summary": {"activeIncidents": 1, "plannedMaintenance": 0, "advisories": 1},
    }
