"""
PagerDuty Integration.
Triggers incidents and retrieves active on-call status.
Replace mock implementations with real PagerDuty API v2 calls.
"""
import json
import requests
from datetime import datetime, timedelta
from config import config


def trigger_incident(title: str, severity: str, details: dict, dedup_key: str = None) -> dict:
    """
    Trigger a PagerDuty incident via Events API v2.
    In production, POST to https://events.pagerduty.com/v2/enqueue
    """
    if not config.pagerduty.enabled or not config.pagerduty.api_key:
        return _mock_trigger(title, severity, details, dedup_key)

    payload = {
        "routing_key":  config.pagerduty.api_key,
        "event_action": "trigger",
        "dedup_key":    dedup_key or f"bank-ops-{datetime.utcnow().timestamp()}",
        "payload": {
            "summary":   title,
            "severity":  severity.lower(),
            "source":    "bank-it-monitoring",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "custom_details": details,
        },
        "links": [{"href": "http://localhost:5000", "text": "Open Dashboard"}],
    }
    try:
        resp = requests.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload, timeout=10,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return {"status": "triggered", "dedup_key": payload["dedup_key"], "response": resp.json()}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_active_incidents() -> list[dict]:
    """
    Retrieve currently active PagerDuty incidents.
    In production: GET https://api.pagerduty.com/incidents?statuses[]=triggered&statuses[]=acknowledged
    """
    if not config.pagerduty.enabled or not config.pagerduty.api_key:
        return _mock_active_incidents()

    headers = {
        "Authorization": f"Token token={config.pagerduty.api_key}",
        "Accept":        "application/vnd.pagerduty+json;version=2",
    }
    try:
        resp = requests.get(
            "https://api.pagerduty.com/incidents",
            headers=headers,
            params={"statuses[]": ["triggered", "acknowledged"]},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("incidents", [])
    except Exception:
        return _mock_active_incidents()


def resolve_incident(dedup_key: str) -> dict:
    """Resolve a PagerDuty incident by dedup key."""
    if not config.pagerduty.enabled:
        return {"status": "resolved (mock)", "dedup_key": dedup_key}
    payload = {
        "routing_key":  config.pagerduty.api_key,
        "event_action": "resolve",
        "dedup_key":    dedup_key,
    }
    try:
        resp = requests.post("https://events.pagerduty.com/v2/enqueue", json=payload, timeout=10)
        resp.raise_for_status()
        return {"status": "resolved", "dedup_key": dedup_key}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Mock implementations
# ---------------------------------------------------------------------------

def _mock_trigger(title, severity, details, dedup_key):
    key = dedup_key or f"mock-{datetime.utcnow().timestamp():.0f}"
    print(f"  [PagerDuty MOCK] Would page on-call: [{severity.upper()}] {title}")
    return {"status": "triggered (mock)", "dedup_key": key, "message": "PagerDuty disabled -- set PAGERDUTY_ENABLED=true and PAGERDUTY_API_KEY to page for real"}


def _mock_active_incidents():
    now = datetime.utcnow()
    return [
        {"id": "PD-Q4AB8WX", "title": "Payment Gateway Degradation",    "severity": "critical", "status": "triggered",     "created_at": (now - timedelta(minutes=23)).isoformat(), "assigned_to": "payments-oncall", "escalation_policy": "Payments P1"},
        {"id": "PD-R7CD9YZ", "title": "Active Credential Stuffing Attack","severity": "high",     "status": "acknowledged",  "created_at": (now - timedelta(minutes=42)).isoformat(), "assigned_to": "soc-oncall",      "escalation_policy": "Security P1"},
        {"id": "PD-S2EF0AB", "title": "Core Banking DB Degradation",     "severity": "high",     "status": "triggered",     "created_at": (now - timedelta(minutes=8)).isoformat(),  "assigned_to": "dba-oncall",      "escalation_policy": "DBA On-Call"},
    ]


def get_mock_pagerduty_status() -> dict:
    """Dashboard-friendly PagerDuty status snapshot."""
    now = datetime.utcnow()
    return {
        "enabled":          config.pagerduty.enabled,
        "active_incidents": _mock_active_incidents(),
        "oncall_now": [
            {"team": "Payments Engineering", "user": "Alex K.",   "escalation_level": 1},
            {"team": "SOC",                  "user": "Maya R.",   "escalation_level": 1},
            {"team": "DBA",                  "user": "Carlos M.", "escalation_level": 1},
            {"team": "SRE / Platform",       "user": "Sam T.",    "escalation_level": 1},
        ],
        "last_checked": now.isoformat(),
    }
