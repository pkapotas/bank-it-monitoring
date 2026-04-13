"""
Kibana / Elasticsearch API tool definitions for the monitoring agent.

Replace mock implementations with real Elasticsearch client calls:
  from elasticsearch import Elasticsearch
  es = Elasticsearch(config.kibana.elasticsearch_url, api_key=config.kibana.api_key)
"""
import json
from datetime import datetime, timedelta

from config import config


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

KIBANA_TOOLS = [
    {
        "name": "kibana_search_logs",
        "description": (
            "Search application and infrastructure logs in Elasticsearch/Kibana using "
            "Lucene query syntax or structured filters. Returns matching log entries with "
            "timestamps, log levels, service names, and full messages. "
            "Use for error investigation, tracing specific transactions, and root cause analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Lucene/KQL query string (e.g., 'level:ERROR AND service:payment-gateway', 'transaction_id:TXN-98765')"
                },
                "index_pattern": {
                    "type": "string",
                    "description": "Elasticsearch index pattern to search (e.g., 'bank-app-logs-*', 'bank-security-*', 'bank-audit-*')",
                    "default": "bank-app-logs-*"
                },
                "time_range_minutes": {
                    "type": "integer",
                    "description": "How many minutes back to search",
                    "default": 60
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of log entries to return",
                    "default": 20
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "kibana_get_error_rate_aggregation",
        "description": (
            "Aggregate error rates by service from Elasticsearch logs over a time window. "
            "Returns error count, warning count, total requests, and error percentage per service. "
            "Useful for identifying which services are producing the most errors."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range_minutes": {
                    "type": "integer",
                    "description": "Time window for aggregation in minutes",
                    "default": 60
                },
                "service_filter": {
                    "type": "string",
                    "description": "Filter to specific service name. Leave empty for all services."
                }
            },
            "required": []
        }
    },
    {
        "name": "kibana_get_security_events",
        "description": (
            "Retrieve security-relevant events from Kibana SIEM indices: "
            "failed authentication attempts, privilege escalation events, "
            "suspicious API access patterns, PCI-DSS violations, and anomalous data access. "
            "Critical for fraud detection and compliance monitoring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "enum": ["authentication_failure", "privilege_escalation", "data_exfiltration", "anomalous_access", "pci_violation", "ALL"],
                    "description": "Type of security event to retrieve",
                    "default": "ALL"
                },
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "ALL"],
                    "description": "Minimum severity level",
                    "default": "high"
                },
                "time_range_hours": {
                    "type": "integer",
                    "description": "How many hours back to retrieve security events",
                    "default": 1
                }
            },
            "required": []
        }
    },
    {
        "name": "kibana_get_transaction_analytics",
        "description": (
            "Analyse banking transaction logs: transaction volumes, failure rates, "
            "processing times, geographic distribution, and anomalies. "
            "Includes payment transactions, fund transfers, ATM withdrawals, and SWIFT messages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_type": {
                    "type": "string",
                    "enum": ["payment", "transfer", "atm_withdrawal", "swift", "all"],
                    "description": "Type of banking transaction to analyze",
                    "default": "all"
                },
                "time_range_minutes": {
                    "type": "integer",
                    "description": "Time window for transaction analysis",
                    "default": 60
                }
            },
            "required": []
        }
    },
    {
        "name": "kibana_get_alert_rules_status",
        "description": (
            "Check the status of Kibana alerting rules and detect muted, failed, "
            "or recently triggered rules. Returns rule names, last execution time, "
            "execution status, and alert counts. Useful for verifying monitoring coverage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rule_category": {
                    "type": "string",
                    "enum": ["security", "performance", "availability", "compliance", "ALL"],
                    "description": "Filter alert rules by category",
                    "default": "ALL"
                }
            },
            "required": []
        }
    },
    {
        "name": "kibana_get_apm_traces",
        "description": (
            "Retrieve distributed traces from Kibana APM for transaction-level visibility. "
            "Returns trace spans, service dependencies, slow spans, and error details "
            "for a specific transaction or service endpoint."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Service name to retrieve traces for"
                },
                "transaction_name": {
                    "type": "string",
                    "description": "Specific transaction/endpoint name (e.g., 'POST /v2/payments/transfer')"
                },
                "time_range_minutes": {
                    "type": "integer",
                    "description": "Time range for trace retrieval",
                    "default": 30
                },
                "min_duration_ms": {
                    "type": "integer",
                    "description": "Only return traces slower than this threshold (ms)",
                    "default": 1000
                }
            },
            "required": ["service_name"]
        }
    }
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def execute_kibana_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a Kibana tool call and return a JSON string result."""
    handlers = {
        "kibana_search_logs": _search_logs,
        "kibana_get_error_rate_aggregation": _get_error_rate_aggregation,
        "kibana_get_security_events": _get_security_events,
        "kibana_get_transaction_analytics": _get_transaction_analytics,
        "kibana_get_alert_rules_status": _get_alert_rules_status,
        "kibana_get_apm_traces": _get_apm_traces,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown Kibana tool: {tool_name}"})
    try:
        result = handler(**tool_input)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Mock implementations
# ---------------------------------------------------------------------------

def _search_logs(query: str, index_pattern="bank-app-logs-*", time_range_minutes=60, max_results=20) -> dict:
    now = datetime.utcnow()
    q_lower = query.lower()
    if "error" in q_lower or "payment-gateway" in q_lower:
        hits = [
            {"@timestamp": (now - timedelta(minutes=5)).isoformat(), "level": "ERROR", "service": "payment-gateway", "message": "ConnectTimeout: upstream clearing-house-api failed to respond within 30000ms", "traceId": "abc123def456", "transactionId": "TXN-98234"},
            {"@timestamp": (now - timedelta(minutes=8)).isoformat(), "level": "ERROR", "service": "payment-gateway", "message": "CircuitBreaker OPEN for clearing-house-api -- 10 consecutive failures", "traceId": "xyz789abc123", "transactionId": None},
            {"@timestamp": (now - timedelta(minutes=11)).isoformat(), "level": "WARN",  "service": "payment-gateway", "message": "Retry attempt 3/3 for transaction TXN-98180 -- last error: HTTP 503", "traceId": "def456xyz789", "transactionId": "TXN-98180"},
            {"@timestamp": (now - timedelta(minutes=14)).isoformat(), "level": "ERROR", "service": "transaction-processor", "message": "Failed to enqueue transaction to Kafka -- broker unavailable", "traceId": "ghi012jkl345", "transactionId": "TXN-98110"},
        ]
    elif "core-banking" in q_lower or "sql" in q_lower:
        hits = [
            {"@timestamp": (now - timedelta(minutes=3)).isoformat(), "level": "ERROR", "service": "core-banking-api", "message": "SQLTimeout: query 'SELECT * FROM ACCOUNTS WHERE customer_id=?' exceeded 10000ms", "query_hash": "a1b2c3d4", "duration_ms": 10243},
            {"@timestamp": (now - timedelta(minutes=9)).isoformat(), "level": "WARN",  "service": "core-banking-api", "message": "Slow query detected (8430ms): missing index hint on TRANSACTIONS table", "query_hash": "e5f6a7b8", "duration_ms": 8430},
        ]
    else:
        hits = [
            {"@timestamp": now.isoformat(), "level": "INFO", "service": "unknown", "message": f"Log search results for: {query}"},
        ]
    return {
        "indexPattern": index_pattern,
        "query": query,
        "timeRangeMinutes": time_range_minutes,
        "totalHits": len(hits) + 142,
        "returnedHits": len(hits),
        "hits": hits,
    }


def _get_error_rate_aggregation(time_range_minutes=60, service_filter=None) -> dict:
    services = [
        {"service": "payment-gateway",        "totalRequests": 110400, "errors": 5189, "warnings": 2340, "errorRate": 4.70, "trend": "increasing"},
        {"service": "core-banking-api",        "totalRequests": 187200, "errors": 562,  "warnings": 1890, "errorRate": 0.30, "trend": "stable"},
        {"service": "fraud-detection",         "totalRequests": 588000, "errors": 588,  "warnings": 294,  "errorRate": 0.10, "trend": "stable"},
        {"service": "authentication-service",  "totalRequests": 858000, "errors": 429,  "warnings": 858,  "errorRate": 0.05, "trend": "stable"},
        {"service": "transaction-processor",   "totalRequests": 147000, "errors": 1764, "warnings": 2940, "errorRate": 1.20, "trend": "stable"},
        {"service": "account-management",      "totalRequests": 336000, "errors": 672,  "warnings": 1008, "errorRate": 0.20, "trend": "stable"},
        {"service": "swift-connector",         "totalRequests": 20400,  "errors": 163,  "warnings": 306,  "errorRate": 0.80, "trend": "stable"},
        {"service": "atm-network",             "totalRequests": 49200,  "errors": 1033, "warnings": 984,  "errorRate": 2.10, "trend": "increasing"},
    ]
    if service_filter:
        services = [s for s in services if service_filter.lower() in s["service"].lower()]
    return {
        "timeRangeMinutes": time_range_minutes,
        "aggregation": services,
        "topErrorServices": [s["service"] for s in sorted(services, key=lambda x: x["errorRate"], reverse=True)[:3]],
    }


def _get_security_events(event_type="ALL", severity="high", time_range_hours=1) -> dict:
    now = datetime.utcnow()
    events = [
        {
            "id": "sec-evt-001",
            "type": "authentication_failure",
            "severity": "high",
            "timestamp": (now - timedelta(minutes=42)).isoformat(),
            "sourceIp": "185.220.101.47",
            "targetService": "authentication-service",
            "userId": None,
            "description": "Credential stuffing attack detected -- 87 failed login attempts from Tor exit node 185.220.101.47",
            "geoLocation": {"country": "Unknown", "isp": "Tor Project"},
            "ruleId": "BRUTE_FORCE_001",
        },
        {
            "id": "sec-evt-002",
            "type": "anomalous_access",
            "severity": "critical",
            "timestamp": (now - timedelta(minutes=15)).isoformat(),
            "sourceIp": "10.0.5.23",
            "targetService": "account-management",
            "userId": "svc-batch-processor",
            "description": "Service account 'svc-batch-processor' accessing customer PII fields outside scheduled batch window (02:00-04:00 UTC). Accessed 1,240 customer records in 3 minutes.",
            "ruleId": "ANOMALOUS_ACCESS_003",
        },
        {
            "id": "sec-evt-003",
            "type": "pci_violation",
            "severity": "critical",
            "timestamp": (now - timedelta(minutes=8)).isoformat(),
            "sourceIp": "10.0.2.45",
            "targetService": "payment-gateway",
            "userId": "dev-user-042",
            "description": "PAN (Primary Account Number) detected in application log entry -- potential PCI-DSS violation. Log file: /var/log/payment-gateway/debug-2026-04-13.log",
            "ruleId": "PCI_DSS_003_3",
        },
    ]
    return {
        "timeRangeHours": time_range_hours,
        "totalEvents": len(events),
        "events": events,
        "summary": {"critical": 2, "high": 1, "medium": 4, "low": 8},
        "threatLevel": "HIGH",
    }


def _get_transaction_analytics(transaction_type="all", time_range_minutes=60) -> dict:
    return {
        "timeRangeMinutes": time_range_minutes,
        "transactionTypes": {
            "payment": {
                "total": 18420, "successful": 17554, "failed": 866,
                "failureRate": 4.70, "avgProcessingTime_ms": 1240,
                "totalValueEUR": 24_560_000,
                "anomalies": ["Failure rate 4.7% exceeds baseline of 0.3%", "Average processing time up 340ms from baseline"],
            },
            "transfer": {
                "total": 5840, "successful": 5805, "failed": 35,
                "failureRate": 0.60, "avgProcessingTime_ms": 890,
                "totalValueEUR": 87_200_000,
                "anomalies": [],
            },
            "atm_withdrawal": {
                "total": 8200, "successful": 8028, "failed": 172,
                "failureRate": 2.10, "avgProcessingTime_ms": 2140,
                "totalValueEUR": 4_100_000,
                "anomalies": ["ATM failure rate elevated -- check network connectivity"],
            },
            "swift": {
                "total": 340, "successful": 337, "failed": 3,
                "failureRate": 0.88, "avgProcessingTime_ms": 4200,
                "totalValueEUR": 156_000_000,
                "anomalies": [],
            },
        },
        "overallStats": {
            "totalTransactions": 32800,
            "overallFailureRate": 3.29,
            "highValueAlerts": 2,
        },
    }


def _get_alert_rules_status(rule_category="ALL") -> dict:
    now = datetime.utcnow()
    rules = [
        {"id": "rule-001", "name": "Payment Error Rate > 2%",         "category": "performance",  "status": "active",  "lastFired": (now - timedelta(minutes=5)).isoformat(),  "executionStatus": "succeeded", "firesLast1h": 12},
        {"id": "rule-002", "name": "Credential Stuffing Detection",   "category": "security",     "status": "active",  "lastFired": (now - timedelta(minutes=42)).isoformat(), "executionStatus": "succeeded", "firesLast1h": 1},
        {"id": "rule-003", "name": "PCI-DSS PAN in Logs",             "category": "compliance",   "status": "active",  "lastFired": (now - timedelta(minutes=8)).isoformat(),  "executionStatus": "succeeded", "firesLast1h": 1},
        {"id": "rule-004", "name": "Core Banking API Latency > 2s",   "category": "performance",  "status": "active",  "lastFired": (now - timedelta(minutes=3)).isoformat(),  "executionStatus": "succeeded", "firesLast1h": 8},
        {"id": "rule-005", "name": "ATM Network Availability < 99%",  "category": "availability", "status": "active",  "lastFired": (now - timedelta(minutes=30)).isoformat(), "executionStatus": "succeeded", "firesLast1h": 4},
        {"id": "rule-006", "name": "Fraud Score Spike Detection",     "category": "security",     "status": "muted",   "lastFired": None,  "executionStatus": "muted", "firesLast1h": 0, "muteReason": "Maintenance window"},
        {"id": "rule-007", "name": "SWIFT Deadline Breach",           "category": "compliance",   "status": "error",   "lastFired": None,  "executionStatus": "failed", "firesLast1h": 0, "error": "Elasticsearch connection refused"},
    ]
    return {
        "totalRules": len(rules),
        "summary": {"active": 5, "muted": 1, "error": 1},
        "rules": rules,
        "attention": ["Rule 'SWIFT Deadline Breach' is failing -- fix Elasticsearch connectivity", "Rule 'Fraud Score Spike Detection' is muted -- verify this is intentional"],
    }


def _get_apm_traces(service_name: str, transaction_name=None, time_range_minutes=30, min_duration_ms=1000) -> dict:
    now = datetime.utcnow()
    return {
        "serviceName": service_name,
        "transactionName": transaction_name or "ALL",
        "timeRangeMinutes": time_range_minutes,
        "minDurationMs": min_duration_ms,
        "traces": [
            {
                "traceId": "abc123def456789",
                "transactionId": "TXN-98234",
                "duration_ms": 3840,
                "result": "failure",
                "timestamp": (now - timedelta(minutes=5)).isoformat(),
                "spans": [
                    {"name": "POST /v2/payments/transfer", "duration_ms": 3840, "service": "payment-gateway"},
                    {"name": "validate_payment_request",   "duration_ms": 12,   "service": "payment-gateway"},
                    {"name": "check_fraud_score",          "duration_ms": 38,   "service": "fraud-detection"},
                    {"name": "debit_account",              "duration_ms": 1840, "service": "core-banking-api", "slowSpan": True, "issue": "SQL query timeout"},
                    {"name": "POST /api/submit",           "duration_ms": 1950, "service": "clearing-house-connector", "error": "ConnectTimeout after 30000ms"},
                ],
                "rootCause": "clearing-house-connector timeout",
            },
        ],
        "statistics": {
            "totalTraces": 47,
            "avgDuration_ms": 2340,
            "p99Duration_ms": 4100,
            "errorRate": 8.5,
        },
    }
