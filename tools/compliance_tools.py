"""
PCI-DSS Compliance Tool Definitions. 6 tools for the Compliance agent.
Covers PCI-DSS requirements 1, 6, 7, 8, 10, 11.
"""
import json
from datetime import datetime, timedelta

COMPLIANCE_TOOLS = [
    {
        "name": "compliance_get_pci_scorecard",
        "description": "Return the current PCI-DSS compliance scorecard scoring all 12 requirements.",
        "input_schema": {"type": "object", "properties": {"requirements": {"type": "array", "items": {"type": "string"}, "description": "Specific requirement numbers to check. Empty for all."}}, "required": []},
    },
    {
        "name": "compliance_get_encryption_status",
        "description": "Check encryption-at-rest and in-transit status for all data stores and API endpoints (PCI-DSS Req 3 & 4).",
        "input_schema": {"type": "object", "properties": {"scope": {"type": "string", "enum": ["databases", "apis", "storage", "all"], "default": "all"}}, "required": []},
    },
    {
        "name": "compliance_get_access_control_review",
        "description": "Review IAM policies, least-privilege violations, and stale access rights (PCI-DSS Req 7 & 8).",
        "input_schema": {"type": "object", "properties": {"scope": {"type": "string", "enum": ["service_accounts", "human_users", "all"], "default": "all"}}, "required": []},
    },
    {
        "name": "compliance_get_vulnerability_scan",
        "description": "Retrieve latest vulnerability scan results for all in-scope PCI systems (PCI-DSS Req 6 & 11).",
        "input_schema": {"type": "object", "properties": {"severity_filter": {"type": "string", "enum": ["critical", "high", "all"], "default": "high"}, "days_since_scan": {"type": "integer", "default": 30}}, "required": []},
    },
    {
        "name": "compliance_get_network_segmentation",
        "description": "Verify network segmentation between CDE (Cardholder Data Environment) and other zones (PCI-DSS Req 1).",
        "input_schema": {"type": "object", "properties": {"check_type": {"type": "string", "enum": ["firewall_rules", "network_flows", "all"], "default": "all"}}, "required": []},
    },
    {
        "name": "compliance_get_pen_test_status",
        "description": "Return the status of penetration testing schedule and latest findings (PCI-DSS Req 11.3).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def execute_compliance_tool(tool_name: str, tool_input: dict) -> str:
    handlers = {
        "compliance_get_pci_scorecard":         _get_pci_scorecard,
        "compliance_get_encryption_status":     _get_encryption_status,
        "compliance_get_access_control_review": _get_access_control_review,
        "compliance_get_vulnerability_scan":    _get_vulnerability_scan,
        "compliance_get_network_segmentation":  _get_network_segmentation,
        "compliance_get_pen_test_status":       _get_pen_test_status,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown compliance tool: {tool_name}"})
    try:
        return json.dumps(handler(**tool_input), default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _get_pci_scorecard(requirements=None):
    now = datetime.utcnow()
    reqs = [
        {"req": "1",  "title": "Install and maintain network controls",          "score": 92, "status": "pass",     "findings": 1, "detail": "1 low-risk firewall rule allows overly broad access to DMZ"},
        {"req": "2",  "title": "Apply secure configurations",                    "score": 88, "status": "pass",     "findings": 2, "detail": "2 services running with default credentials in staging"},
        {"req": "3",  "title": "Protect stored account data",                    "score": 45, "status": "FAIL",     "findings": 1, "detail": "CRITICAL: PAN found in payment-gateway debug log (unmasked)"},
        {"req": "4",  "title": "Protect cardholder data in transit",             "score": 95, "status": "pass",     "findings": 0, "detail": "All endpoints using TLS 1.2+"},
        {"req": "5",  "title": "Protect systems against malicious software",     "score": 90, "status": "pass",     "findings": 1, "detail": "AV definition update delayed on 2 hosts"},
        {"req": "6",  "title": "Develop and maintain secure systems",            "score": 78, "status": "warning",  "findings": 3, "detail": "3 HIGH CVEs unpatched > 30 days in CDE"},
        {"req": "7",  "title": "Restrict access by business need",               "score": 72, "status": "warning",  "findings": 4, "detail": "4 service accounts with excessive privilege"},
        {"req": "8",  "title": "Identify users and authenticate access",          "score": 85, "status": "pass",     "findings": 2, "detail": "2 shared accounts still active; MFA not enforced on 1 admin console"},
        {"req": "9",  "title": "Restrict physical access",                        "score": 98, "status": "pass",     "findings": 0, "detail": "All data centre access compliant"},
        {"req": "10", "title": "Log and monitor all access",                      "score": 62, "status": "warning",  "findings": 2, "detail": "SWIFT alert rule failing; 4h audit gap. Log retention only 89 days (need 90)."},
        {"req": "11", "title": "Test security of systems and networks regularly", "score": 80, "status": "pass",     "findings": 1, "detail": "Quarterly pen test overdue by 12 days"},
        {"req": "12", "title": "Support information security with policies",       "score": 94, "status": "pass",     "findings": 0, "detail": "Policies current and signed"},
    ]
    overall = sum(r["score"] for r in reqs) / len(reqs)
    fails   = [r for r in reqs if r["status"] == "FAIL"]
    warns   = [r for r in reqs if r["status"] == "warning"]
    return {
        "generated_at":    now.isoformat(),
        "overall_score":   round(overall, 1),
        "overall_status":  "NON_COMPLIANT" if fails else ("WARNING" if warns else "COMPLIANT"),
        "requirements":    reqs,
        "summary":         {"pass": sum(1 for r in reqs if r["status"] == "pass"), "warning": len(warns), "fail": len(fails)},
        "critical_action": "Req 3: Remove PAN from debug logs immediately and file PCI incident report within 72 hours",
    }


def _get_encryption_status(scope="all"):
    return {
        "databases": [
            {"name": "ORACLE-CORE-BANKING", "encryption_at_rest": "AES-256 TDE", "status": "compliant", "key_rotation_days": 90},
            {"name": "SQLSERVER-FRAUD-DB",  "encryption_at_rest": "AES-256 TDE", "status": "compliant", "key_rotation_days": 90},
            {"name": "REDIS-SESSION",       "encryption_at_rest": "None",        "status": "WARNING",   "finding": "Session cache not encrypted at rest -- contains session tokens"},
        ],
        "api_endpoints": [
            {"endpoint": "payment-gateway /v2/transfers", "tls_version": "TLS 1.3", "status": "compliant"},
            {"endpoint": "core-banking-api /accounts",    "tls_version": "TLS 1.2", "status": "compliant"},
            {"endpoint": "internal-admin /debug",         "tls_version": "HTTP",    "status": "FAIL", "finding": "Admin endpoint exposed over plaintext HTTP on internal network"},
        ],
        "summary": {"compliant": 4, "warning": 1, "fail": 1},
    }


def _get_access_control_review(scope="all"):
    return {
        "over_privileged_accounts": [
            {"account": "svc-batch-processor", "type": "service", "issue": "Has SELECT ANY TABLE on ORACLE-CORE-BANKING; only needs 3 specific tables", "risk": "high"},
            {"account": "dev-user-042",         "type": "human",   "issue": "Production KeyVault access granted for debugging 6 months ago, never revoked", "risk": "high"},
            {"account": "svc-monitoring",       "type": "service", "issue": "Has write access to audit logs (should be read-only)", "risk": "critical"},
            {"account": "svc-reporting",        "type": "service", "issue": "Access to SWIFT message store not required for reporting function", "risk": "medium"},
        ],
        "stale_accounts": [
            {"account": "contractor-user-99", "last_login": "2025-12-14", "days_inactive": 120, "access_level": "read-only prod"},
            {"account": "temp-dev-003",        "last_login": "2026-01-02", "days_inactive": 101, "access_level": "dev environment"},
        ],
        "summary": {"over_privileged": 4, "stale": 2, "shared_accounts": 1},
    }


def _get_vulnerability_scan(severity_filter="high", days_since_scan=30):
    now = datetime.utcnow()
    return {
        "last_scan": (now - timedelta(days=12)).isoformat(),
        "scan_tool": "Tenable.io",
        "vulnerabilities": [
            {"cve": "CVE-2024-3094", "cvss": 10.0, "severity": "critical", "component": "liblzma 5.6.0", "hosts": ["fraud-ml-node-01", "core-db-primary-01"], "days_open": 18, "patch_available": True},
            {"cve": "CVE-2024-6387", "cvss": 8.1,  "severity": "high",     "component": "OpenSSH < 9.8p1", "hosts": ["atm-gateway-02", "payment-gw-node-01"], "days_open": 34, "patch_available": True},
            {"cve": "CVE-2023-44487", "cvss": 7.5, "severity": "high",     "component": "HTTP/2 (nginx 1.24)", "hosts": ["payment-gw-node-01", "core-banking-app-01"], "days_open": 45, "patch_available": True},
        ],
        "summary": {"critical": 1, "high": 2, "medium": 7, "low": 14},
        "overdue_patches": 3,
    }


def _get_network_segmentation():
    return {
        "cde_zones": ["payment-gateway-subnet", "core-banking-subnet", "card-processing-subnet"],
        "checks": [
            {"check": "CDE to internet", "expected": "BLOCKED", "actual": "BLOCKED", "status": "pass"},
            {"check": "CDE to corporate LAN", "expected": "BLOCKED", "actual": "ALLOWED (8 rules)", "status": "WARNING", "detail": "8 firewall rules allow corporate -> CDE; 2 appear overly broad"},
            {"check": "Dev environment to CDE", "expected": "BLOCKED", "actual": "BLOCKED", "status": "pass"},
            {"check": "Monitoring subnet to CDE", "expected": "READ-ONLY", "actual": "ALLOWED (all ports)", "status": "WARNING", "detail": "Monitoring agents have full network access to CDE hosts"},
        ],
        "summary": {"pass": 2, "warning": 2, "fail": 0},
    }


def _get_pen_test_status():
    now = datetime.utcnow()
    return {
        "last_external_pentest": (now - timedelta(days=102)).isoformat(),
        "last_internal_pentest": (now - timedelta(days=78)).isoformat(),
        "schedule_requirement": "Quarterly",
        "days_overdue_external": 12,
        "days_overdue_internal": 0,
        "last_findings": [
            {"severity": "high",   "title": "SQL injection in legacy account-management API v1", "status": "remediated", "remediated_date": (now - timedelta(days=45)).isoformat()},
            {"severity": "medium", "title": "Missing rate limiting on authentication-service",    "status": "open",        "due_date": (now + timedelta(days=14)).isoformat()},
        ],
        "open_findings": 1,
        "status": "OVERDUE",
        "action_required": "Schedule external penetration test within 18 days to remain PCI-DSS compliant",
    }
