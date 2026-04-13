"""
Runbook Executor — safe automated remediation with approval flow.

Approval flow:
1. Claude detects issue and identifies applicable runbook
2. If requires_approval=True: post Slack approval request, set status=PENDING_APPROVAL
3. On Slack APPROVE button: execute action, log result
4. On Slack DENY button: cancel, log reason
5. If requires_approval=False and risk=low: auto-execute, notify Slack
"""
import json
import subprocess
from datetime import datetime
from typing import Optional
from runbooks.catalogue import get_runbook, RUNBOOKS
from integrations.slack import post_runbook_approval, post_alert

# In-memory queue (replace with Redis or DB in production)
_approval_queue: dict[str, dict] = {}
_execution_log: list[dict] = []


def request_runbook_execution(runbook_id: str, triggered_by: str, incident_id: str = None) -> dict:
    """
    Request execution of a runbook. Routes to auto-execute or approval flow
    based on risk level and requires_approval flag.
    """
    rb = get_runbook(runbook_id)
    if not rb:
        return {"status": "error", "message": f"Runbook {runbook_id} not found"}

    entry = {
        "id":           f"REQ-{len(_execution_log)+1:04d}",
        "runbook_id":   runbook_id,
        "runbook_name": rb["name"],
        "service":      rb["service"],
        "action":       rb["action"],
        "risk":         rb["risk"],
        "triggered_by": triggered_by,
        "incident_id":  incident_id,
        "requested_at": datetime.utcnow().isoformat(),
        "status":       None,
    }

    if rb["requires_approval"]:
        entry["status"] = "PENDING_APPROVAL"
        _approval_queue[entry["id"]] = entry
        # Notify Slack
        post_runbook_approval(
            runbook_id  = entry["id"],
            action      = rb["action"],
            service     = rb["service"],
            reason      = f"Auto-detected issue requires remediation. Triggered by: {triggered_by}",
        )
        _execution_log.append(entry)
        return {"status": "PENDING_APPROVAL", "request_id": entry["id"], "runbook": rb["name"]}
    else:
        # Auto-execute low-risk runbooks
        entry["status"] = "AUTO_EXECUTING"
        result = _execute(rb, dry_run=True)   # dry_run=True in demo mode
        entry["status"] = "COMPLETED" if result["success"] else "FAILED"
        entry["result"] = result
        entry["executed_at"] = datetime.utcnow().isoformat()
        _execution_log.append(entry)
        post_alert(
            title    = f"Auto-executed: {rb['name']}",
            severity = "info",
            body     = f"Runbook {runbook_id} executed automatically for {rb['service']}.\nAction: {rb['action'][:100]}\nResult: {result['message']}",
        )
        return {"status": entry["status"], "request_id": entry["id"], "runbook": rb["name"], "result": result}


def approve_runbook(request_id: str, approved_by: str) -> dict:
    """Approve and execute a pending runbook."""
    entry = _approval_queue.get(request_id)
    if not entry:
        return {"status": "error", "message": f"Request {request_id} not found or already processed"}

    rb = get_runbook(entry["runbook_id"])
    entry["status"]      = "EXECUTING"
    entry["approved_by"] = approved_by
    entry["approved_at"] = datetime.utcnow().isoformat()

    result = _execute(rb, dry_run=True)
    entry["status"]      = "COMPLETED" if result["success"] else "FAILED"
    entry["result"]      = result
    entry["executed_at"] = datetime.utcnow().isoformat()
    del _approval_queue[request_id]

    post_alert(title=f"Runbook executed: {rb['name']}", severity="info",
               body=f"Approved by {approved_by}. Result: {result['message']}")
    return {"status": entry["status"], "result": result}


def deny_runbook(request_id: str, denied_by: str, reason: str = "") -> dict:
    """Deny a pending runbook execution."""
    entry = _approval_queue.pop(request_id, None)
    if not entry:
        return {"status": "error", "message": f"Request {request_id} not found"}
    entry["status"]    = "DENIED"
    entry["denied_by"] = denied_by
    entry["deny_reason"] = reason
    entry["denied_at"] = datetime.utcnow().isoformat()
    return {"status": "DENIED", "request_id": request_id}


def get_pending_approvals() -> list[dict]:
    return list(_approval_queue.values())


def get_execution_log(last_n: int = 20) -> list[dict]:
    return list(reversed(_execution_log[-last_n:]))


def _execute(runbook: dict, dry_run: bool = True) -> dict:
    """Execute the runbook action. dry_run=True logs but doesn't actually run the command."""
    if dry_run:
        print(f"  [Runbook DRY-RUN] Would execute: {runbook['action'][:80]}...")
        return {"success": True, "message": f"DRY-RUN: {runbook['action'][:80]}... (not actually executed)", "dry_run": True}
    try:
        result = subprocess.run(
            runbook["action"], shell=True, capture_output=True, text=True, timeout=120
        )
        success = result.returncode == 0
        return {"success": success, "stdout": result.stdout[:500], "stderr": result.stderr[:200], "returncode": result.returncode, "dry_run": False}
    except Exception as e:
        return {"success": False, "message": str(e), "dry_run": False}


def get_mock_runbook_queue() -> dict:
    """Return mock pending approvals for the dashboard."""
    now = datetime.utcnow()
    from datetime import timedelta
    return {
        "pending_approvals": [
            {"id": "REQ-0001", "runbook_id": "RB-002", "runbook_name": "Scale AKS Node Pool",   "service": "payment-gateway-aks",    "risk": "medium", "triggered_by": "Orchestrator (INC-001)", "requested_at": (now - timedelta(minutes=3)).isoformat(),  "action": "az aks nodepool scale --node-count 6"},
            {"id": "REQ-0002", "runbook_id": "RB-003", "runbook_name": "Block IP at WAF",       "service": "authentication-service", "risk": "low",    "triggered_by": "Orchestrator (INC-003)", "requested_at": (now - timedelta(minutes=8)).isoformat(),  "action": "Block 185.220.101.47 at Azure WAF"},
            {"id": "REQ-0003", "runbook_id": "RB-004", "runbook_name": "Flush Oracle Connection Pool", "service": "core-banking-api", "risk": "medium", "triggered_by": "Orchestrator (INC-004)", "requested_at": (now - timedelta(minutes=1)).isoformat(), "action": "exec dbms_shared_pool.purge on CORE-BANKING"},
        ],
        "recently_executed": [
            {"id": "REQ-0000", "runbook_name": "Rotate Payment Gateway Debug Log Level", "service": "payment-gateway", "status": "COMPLETED", "executed_at": (now - timedelta(minutes=6)).isoformat(), "executed_by": "Auto (low-risk)", "result": "Log level reverted to INFO -- PAN exposure stopped"},
            {"id": "REQ-PREV", "runbook_name": "Terminate ML Training Job",             "service": "fraud-detection", "status": "COMPLETED", "executed_at": (now - timedelta(minutes=40)).isoformat(), "executed_by": "Auto (low-risk)", "result": "Training job cancelled; rescheduled for 03:00 UTC"},
        ],
    }
