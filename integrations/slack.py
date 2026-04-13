"""
Slack Integration — ops alerts and runbook approval flow.
Replace mock with real Slack Web API calls (pip install slack-sdk).
"""
import json
import requests
from datetime import datetime
from config import config


def post_alert(title: str, severity: str, body: str, channel: str = None) -> dict:
    """Post an ops alert to the configured Slack channel."""
    ch = channel or config.slack.ops_channel
    if not config.slack.enabled or not config.slack.bot_token:
        return _mock_post(ch, title, severity, body)

    color = {"critical": "#ef4444", "high": "#f97316", "warning": "#eab308", "info": "#22c55e"}.get(severity, "#6366f1")
    payload = {
        "channel": ch,
        "attachments": [{
            "color":   color,
            "title":   f"[{severity.upper()}] {title}",
            "text":    body,
            "footer":  "Bank IT Monitoring | " + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }],
    }
    return _post_to_slack("chat.postMessage", payload)


def post_runbook_approval(runbook_id: str, action: str, service: str, reason: str) -> dict:
    """Post a runbook approval request to the approval channel."""
    ch = config.slack.approval_channel
    if not config.slack.enabled or not config.slack.bot_token:
        return _mock_approval_request(runbook_id, action, service, reason)

    payload = {
        "channel": ch,
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"Runbook Approval Required: {runbook_id}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Service:*\n{service}"},
                {"type": "mrkdwn", "text": f"*Action:*\n{action}"},
                {"type": "mrkdwn", "text": f"*Reason:*\n{reason}"},
                {"type": "mrkdwn", "text": f"*Requested:*\n{datetime.utcnow().strftime('%H:%M UTC')}"},
            ]},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "APPROVE"}, "style": "primary",  "action_id": f"approve_{runbook_id}", "value": runbook_id},
                {"type": "button", "text": {"type": "plain_text", "text": "DENY"},    "style": "danger",   "action_id": f"deny_{runbook_id}",    "value": runbook_id},
            ]},
        ],
    }
    return _post_to_slack("chat.postMessage", payload)


def _post_to_slack(method: str, payload: dict) -> dict:
    try:
        resp = requests.post(
            f"https://slack.com/api/{method}",
            json=payload,
            headers={"Authorization": f"Bearer {config.slack.bot_token}"},
            timeout=10,
        )
        data = resp.json()
        return {"status": "sent" if data.get("ok") else "error", "ts": data.get("ts"), "error": data.get("error")}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _mock_post(channel, title, severity, body):
    print(f"  [Slack MOCK] {channel}: [{severity.upper()}] {title}")
    return {"status": "sent (mock)", "channel": channel}


def _mock_approval_request(runbook_id, action, service, reason):
    print(f"  [Slack MOCK] Approval request: {runbook_id} -- {action} on {service}")
    return {"status": "sent (mock)", "runbook_id": runbook_id, "pending_approval": True}
