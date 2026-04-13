"""
Audit Log Tool Definitions.

Covers PCI-DSS, SOX, GDPR audit trail analysis. 6 tools for the Audit agent.
Replace mock implementations with real Elasticsearch/Splunk queries.
"""
import json
import random
from datetime import datetime, timedelta

AUDIT_TOOLS = [
    {
        "name": "audit_get_privileged_access_log",
        "description": (
            "Retrieve privileged access events: root/admin logins, sudo usage, "
            "service account elevation, and key vault access. Essential for SOX and PCI-DSS audit trails."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range_hours": {"type": "integer", "default": 24},
                "user_filter": {"type": "string", "description": "Filter by specific user or service account"},
                "severity": {"type": "string", "enum": ["all", "suspicious", "critical"], "default": "all"},
            },
            "required": [],
        },
    },
    {
        "name": "audit_get_data_access_log",
        "description": (
            "Track access to sensitive banking data: customer PII, account records, "
            "transaction history. Detects unauthorized bulk access and data exfiltration patterns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range_hours": {"type": "integer", "default": 24},
                "data_classification": {"type": "string", "enum": ["PII", "PAN", "financial", "all"], "default": "all"},
                "min_records_accessed": {"type": "integer", "default": 100, "description": "Flag access of more than N records"},
            },
            "required": [],
        },
    },
    {
        "name": "audit_get_config_changes",
        "description": (
            "Retrieve infrastructure and application configuration changes: "
            "firewall rule edits, IAM policy changes, Kubernetes ConfigMap updates, "
            "database schema modifications. Critical for change management and compliance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range_hours": {"type": "integer", "default": 24},
                "resource_type": {"type": "string", "enum": ["network", "iam", "database", "kubernetes", "all"], "default": "all"},
                "change_type": {"type": "string", "enum": ["create", "update", "delete", "all"], "default": "all"},
            },
            "required": [],
        },
    },
    {
        "name": "audit_get_compliance_violations",
        "description": (
            "Query the audit log for known compliance rule violations: "
            "PCI-DSS (PAN in logs, unencrypted transmission), GDPR (unauthorized PII access), "
            "SOX (financial data modification without approval). Returns violation details and evidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range_hours": {"type": "integer", "default": 24},
                "framework": {"type": "string", "enum": ["PCI-DSS", "GDPR", "SOX", "all"], "default": "all"},
                "severity": {"type": "string", "enum": ["critical", "high", "all"], "default": "all"},
            },
            "required": [],
        },
    },
    {
        "name": "audit_get_failed_auth_summary",
        "description": (
            "Aggregate failed authentication events by user, IP, and target service. "
            "Identifies brute force, credential stuffing, and password spray attacks. "
            "Groups events into attack campaigns by source IP and timing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range_hours": {"type": "integer", "default": 1},
                "min_failures": {"type": "integer", "default": 5, "description": "Minimum failures to include in report"},
                "group_by": {"type": "string", "enum": ["ip", "user", "service"], "default": "ip"},
            },
            "required": [],
        },
    },
    {
        "name": "audit_get_key_vault_access",
        "description": (
            "Retrieve Azure Key Vault and HSM access logs: secret reads, certificate operations, "
            "key usage events. Detects unauthorized secret access and key export attempts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range_hours": {"type": "integer", "default": 24},
                "vault_name": {"type": "string", "description": "Specific vault name, or empty for all vaults"},
                "operation_type": {"type": "string", "enum": ["SecretGet", "KeyDecrypt", "CertificateGet", "all"], "default": "all"},
            },
            "required": [],
        },
    },
]


def execute_audit_tool(tool_name: str, tool_input: dict) -> str:
    handlers = {
        "audit_get_privileged_access_log": _get_privileged_access,
        "audit_get_data_access_log":       _get_data_access,
        "audit_get_config_changes":        _get_config_changes,
        "audit_get_compliance_violations": _get_compliance_violations,
        "audit_get_failed_auth_summary":   _get_failed_auth_summary,
        "audit_get_key_vault_access":      _get_key_vault_access,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown audit tool: {tool_name}"})
    try:
        return json.dumps(handler(**tool_input), default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _get_privileged_access(time_range_hours=24, user_filter=None, severity="all"):
    now = datetime.utcnow()
    events = [
        {"timestamp": (now - timedelta(hours=2)).isoformat(),  "user": "svc-deploy-agent",  "action": "sudo kubectl apply", "target": "payment-gateway-aks", "result": "success", "suspicious": False},
        {"timestamp": (now - timedelta(hours=5)).isoformat(),  "user": "dba-user-007",       "action": "ALTER TABLE ACCOUNTS ADD COLUMN", "target": "ORACLE-CORE-BANKING", "result": "success", "suspicious": False},
        {"timestamp": (now - timedelta(minutes=42)).isoformat(),"user": "dev-user-042",      "action": "READ secret payment-gateway-api-key", "target": "bank-keyvault-prod", "result": "success", "suspicious": True, "reason": "Access outside business hours, no change ticket"},
        {"timestamp": (now - timedelta(hours=18)).isoformat(), "user": "svc-batch-processor","action": "SELECT * FROM CUSTOMERS LIMIT 10000", "target": "ORACLE-CORE-BANKING", "result": "success", "suspicious": True, "reason": "Bulk query outside scheduled batch window"},
    ]
    suspicious_count = sum(1 for e in events if e.get("suspicious"))
    return {"timeRangeHours": time_range_hours, "totalEvents": len(events), "suspiciousEvents": suspicious_count, "events": events}


def _get_data_access(time_range_hours=24, data_classification="all", min_records_accessed=100):
    now = datetime.utcnow()
    return {
        "timeRangeHours": time_range_hours,
        "dataClassification": data_classification,
        "accessEvents": [
            {"timestamp": (now - timedelta(minutes=15)).isoformat(), "user": "svc-batch-processor", "classification": "PII", "records_accessed": 1240, "table": "CUSTOMERS", "suspicious": True, "reason": "Outside scheduled window (02:00-04:00 UTC)"},
            {"timestamp": (now - timedelta(hours=3)).isoformat(),  "user": "analyst-user-12",      "classification": "financial", "records_accessed": 342, "table": "TRANSACTIONS", "suspicious": False, "reason": None},
            {"timestamp": (now - timedelta(minutes=8)).isoformat(), "user": "dev-user-042",        "classification": "PAN", "records_accessed": 1, "table": "payment_gateway.debug_log", "suspicious": True, "reason": "PAN found in unmasked debug log output"},
        ],
        "summary": {"total_pii_accesses": 3, "suspicious": 2, "bulk_access_events": 1},
    }


def _get_config_changes(time_range_hours=24, resource_type="all", change_type="all"):
    now = datetime.utcnow()
    return {
        "changes": [
            {"timestamp": (now - timedelta(hours=6)).isoformat(),  "user": "svc-deploy-agent", "resource": "payment-gateway-aks/deployment.yaml", "type": "update", "detail": "Image updated: v2.3.3 -> v2.3.4", "approved": True, "ticket": "CHG-4821"},
            {"timestamp": (now - timedelta(hours=14)).isoformat(), "user": "dba-user-007",      "resource": "ORACLE-CORE-BANKING/ACCOUNTS", "type": "update", "detail": "Schema change: added column last_login_ip", "approved": True, "ticket": "CHG-4819"},
            {"timestamp": (now - timedelta(minutes=8)).isoformat(), "user": "dev-user-042",     "resource": "payment-gateway/log4j2.xml", "type": "update", "detail": "Log level changed to DEBUG (includes request/response bodies)", "approved": False, "ticket": None, "risk": "HIGH - may expose PAN in logs"},
        ],
        "unapproved_changes": 1,
        "summary": {"total": 3, "approved": 2, "unapproved": 1, "high_risk": 1},
    }


def _get_compliance_violations(time_range_hours=24, framework="all", severity="all"):
    now = datetime.utcnow()
    return {
        "violations": [
            {"id": "VIO-001", "framework": "PCI-DSS", "requirement": "3.3 - Do not store sensitive authentication data", "severity": "critical", "timestamp": (now - timedelta(minutes=8)).isoformat(), "evidence": "PAN found in /var/log/payment-gateway/debug-2026-04-13.log line 4821", "owner": "Security & Compliance", "status": "open", "mandatory_action": "Notify card schemes within 72 hours"},
            {"id": "VIO-002", "framework": "GDPR",    "requirement": "Art 5(1)(b) - Purpose limitation", "severity": "high", "timestamp": (now - timedelta(minutes=15)).isoformat(), "evidence": "svc-batch-processor accessed 1,240 PII records outside scheduled batch job scope", "owner": "Data Protection Officer", "status": "open", "mandatory_action": "Investigate within 24 hours"},
            {"id": "VIO-003", "framework": "PCI-DSS", "requirement": "10.2 - Implement automated audit trails", "severity": "medium", "timestamp": (now - timedelta(hours=6)).isoformat(), "evidence": "Kibana alert rule 'SWIFT Deadline Breach' failed -- audit gap of 4 hours", "owner": "Security Operations", "status": "open", "mandatory_action": "Restore alerting within 4 hours"},
        ],
        "summary": {"total": 3, "critical": 1, "high": 1, "medium": 1},
        "frameworks_affected": ["PCI-DSS", "GDPR"],
        "requires_regulatory_notification": True,
    }


def _get_failed_auth_summary(time_range_hours=1, min_failures=5, group_by="ip"):
    now = datetime.utcnow()
    return {
        "timeRangeHours": time_range_hours,
        "attackCampaigns": [
            {"source_ip": "185.220.101.47", "isp": "Tor Project", "country": "Unknown", "failures": 87, "targeted_users": 23, "targeted_service": "authentication-service", "pattern": "credential stuffing", "first_seen": (now - timedelta(minutes=42)).isoformat(), "last_seen": (now - timedelta(minutes=2)).isoformat(), "blocked": False},
            {"source_ip": "91.108.4.33",    "isp": "Telegram",    "country": "Russia",  "failures": 14, "targeted_users": 14, "targeted_service": "azure-ad",                "pattern": "password spray",       "first_seen": (now - timedelta(minutes=28)).isoformat(), "last_seen": (now - timedelta(minutes=10)).isoformat(), "blocked": False},
        ],
        "totalFailures": 101,
        "uniqueSourceIPs": 2,
        "accountsAtRisk": 37,
    }


def _get_key_vault_access(time_range_hours=24, vault_name=None, operation_type="all"):
    now = datetime.utcnow()
    return {
        "vault": vault_name or "bank-keyvault-prod",
        "accessEvents": [
            {"timestamp": (now - timedelta(minutes=42)).isoformat(), "caller": "dev-user-042", "operation": "SecretGet", "secret_name": "payment-gateway-api-key", "result": "Success", "suspicious": True, "reason": "Access at 23:18 UTC -- outside business hours, no associated deployment"},
            {"timestamp": (now - timedelta(hours=2)).isoformat(),  "caller": "svc-deploy-agent", "operation": "CertificateGet", "secret_name": "payment-gateway-tls-cert", "result": "Success", "suspicious": False},
            {"timestamp": (now - timedelta(hours=6)).isoformat(),  "caller": "svc-backup",        "operation": "KeyDecrypt",      "secret_name": "db-encryption-key",         "result": "Success", "suspicious": False},
        ],
        "suspiciousAccesses": 1,
        "summary": {"total": 3, "suspicious": 1},
    }
