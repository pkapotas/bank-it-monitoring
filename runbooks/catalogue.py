"""
Runbook Catalogue — defines safe automated remediation actions per issue type.
Each runbook specifies: trigger conditions, action, risk level, and approval requirements.
"""
from datetime import datetime

RUNBOOKS = {
    "RB-001": {
        "id":           "RB-001",
        "name":         "Restart Redis Session Cache",
        "service":      "redis-session",
        "trigger":      "connection_pool_pct > 90",
        "action":       "kubectl rollout restart deployment/redis-session -n banking",
        "risk":         "low",
        "requires_approval": False,
        "estimated_downtime_sec": 30,
        "rollback":     "kubectl rollout undo deployment/redis-session -n banking",
        "runbook_url":  "https://wiki.bank.internal/runbooks/redis-restart",
        "description":  "Gracefully restart Redis session cache to clear connection pool backlog. Causes ~30s of session drops (re-login required). Safe during business hours.",
    },
    "RB-002": {
        "id":           "RB-002",
        "name":         "Scale AKS Node Pool",
        "service":      "payment-gateway-aks",
        "trigger":      "pod_pending > 2 OR node_cpu_pct > 85",
        "action":       "az aks nodepool scale --cluster-name payment-gateway-aks --name payments --node-count 6",
        "risk":         "medium",
        "requires_approval": True,
        "estimated_downtime_sec": 0,
        "rollback":     "az aks nodepool scale --cluster-name payment-gateway-aks --name payments --node-count 4",
        "runbook_url":  "https://wiki.bank.internal/runbooks/aks-scale",
        "description":  "Add 2 nodes to payment-gateway AKS node pool. Incurs ~EUR 80/day additional cost. Requires approval.",
    },
    "RB-003": {
        "id":           "RB-003",
        "name":         "Block IP at WAF",
        "service":      "authentication-service",
        "trigger":      "credential_stuffing_detected OR brute_force_detected",
        "action":       "az network application-gateway waf-policy custom-rule create --name BlockIP --priority 1 --rule-type MatchRule --action Block",
        "risk":         "low",
        "requires_approval": True,
        "estimated_downtime_sec": 0,
        "rollback":     "az network application-gateway waf-policy custom-rule delete --name BlockIP",
        "runbook_url":  "https://wiki.bank.internal/runbooks/waf-block",
        "description":  "Add attacker IP to Azure WAF block list. Requires SOC approval to prevent false positive blocking.",
    },
    "RB-004": {
        "id":           "RB-004",
        "name":         "Flush Oracle Connection Pool",
        "service":      "core-banking-api",
        "trigger":      "oracle_connection_pool_pct > 85 OR avg_query_time_ms > 5000",
        "action":       "sqlplus system/<password>@CORE-BANKING \"exec dbms_shared_pool.purge('','C')\"",
        "risk":         "medium",
        "requires_approval": True,
        "estimated_downtime_sec": 120,
        "rollback":     "N/A -- purge is one-way; monitor for recovery",
        "runbook_url":  "https://wiki.bank.internal/runbooks/oracle-pool-flush",
        "description":  "Flush Oracle shared pool and connection cache. May cause 2-min latency spike during re-warming. DBA approval required.",
    },
    "RB-005": {
        "id":           "RB-005",
        "name":         "Rotate Payment Gateway Debug Log Level",
        "service":      "payment-gateway",
        "trigger":      "pci_pan_in_logs OR debug_log_enabled_production",
        "action":       "kubectl set env deployment/payment-gateway LOG_LEVEL=INFO -n banking && kubectl rollout restart deployment/payment-gateway -n banking",
        "risk":         "low",
        "requires_approval": False,
        "estimated_downtime_sec": 30,
        "rollback":     "kubectl set env deployment/payment-gateway LOG_LEVEL=DEBUG -n banking",
        "runbook_url":  "https://wiki.bank.internal/runbooks/log-level-rotate",
        "description":  "Immediately revert payment-gateway log level from DEBUG to INFO. Stops PAN exposure in logs. Causes ~30s rolling restart.",
    },
    "RB-006": {
        "id":           "RB-006",
        "name":         "Terminate ML Training Job",
        "service":      "fraud-detection",
        "trigger":      "ml_training_cpu_pct > 85 OR ml_training_outside_window",
        "action":       "az ml job cancel --name fraud-model-retrain-$(date +%Y%m%d) --resource-group bank-prod-rg --workspace-name bank-ml-workspace",
        "risk":         "low",
        "requires_approval": False,
        "estimated_downtime_sec": 0,
        "rollback":     "az ml job create --file fraud-retrain-config.yml (reschedule for 03:00 UTC)",
        "runbook_url":  "https://wiki.bank.internal/runbooks/ml-job-cancel",
        "description":  "Cancel runaway ML training job consuming excessive CPU on fraud-detection hosts. Reschedule to 03:00-05:00 UTC maintenance window.",
    },
}


def get_applicable_runbooks(issue_type: str, service: str) -> list[dict]:
    """Return runbooks relevant to an issue type and service."""
    results = []
    for rb in RUNBOOKS.values():
        if rb["service"] == service or service in rb["trigger"]:
            results.append(rb)
        elif issue_type.lower() in rb["trigger"].lower() or issue_type.lower() in rb["description"].lower():
            results.append(rb)
    return results


def get_runbook(runbook_id: str) -> dict | None:
    return RUNBOOKS.get(runbook_id)
