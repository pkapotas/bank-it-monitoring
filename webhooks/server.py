"""
Event-Driven Webhook Server.
Receives webhook events from Dynatrace, Azure Monitor, and Kibana.
Immediately triggers the relevant specialist agent instead of waiting for the next cron run.

Register these URLs in your monitoring platforms:
  Dynatrace Problem Notifications -> POST /webhooks/dynatrace
  Azure Monitor Action Groups     -> POST /webhooks/azure
  Kibana Alerting Webhook         -> POST /webhooks/kibana
"""
import json
import threading
from datetime import datetime
from flask import Blueprint, request, jsonify

webhooks_bp = Blueprint("webhooks", __name__)

# In-memory event queue (replace with Redis/Kafka in production)
_event_queue: list[dict] = []
_event_lock  = threading.Lock()


def _queue_event(source: str, payload: dict) -> None:
    with _event_lock:
        _event_queue.append({
            "id":        f"EVT-{len(_event_queue)+1:05d}",
            "source":    source,
            "received":  datetime.utcnow().isoformat(),
            "payload":   payload,
            "processed": False,
        })
    # In production: trigger agent async via Celery/RQ task queue
    # from agents.dynatrace_agent import run_dynatrace_agent
    # threading.Thread(target=run_dynatrace_agent, daemon=True).start()
    print(f"  [Webhook] Queued {source} event: {payload.get('title', payload.get('summary', ''))[:60]}")


@webhooks_bp.route("/webhooks/dynatrace", methods=["POST"])
def dynatrace_webhook():
    """Receive Dynatrace Problem Notifications."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    # Normalize Dynatrace webhook format
    event = {
        "title":     data.get("ProblemTitle", data.get("title", "Unknown problem")),
        "id":        data.get("ProblemID", ""),
        "severity":  data.get("ProblemSeverity", "").lower(),
        "state":     data.get("State", "OPEN"),
        "impact":    data.get("ProblemImpact", ""),
        "url":       data.get("ProblemURL", ""),
    }
    _queue_event("dynatrace", event)
    return jsonify({"status": "queued", "event_id": f"EVT-{len(_event_queue):05d}"}), 200


@webhooks_bp.route("/webhooks/azure", methods=["POST"])
def azure_webhook():
    """Receive Azure Monitor Action Group alerts."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    # Azure Common Alert Schema
    essentials = data.get("data", {}).get("essentials", data)
    event = {
        "title":      essentials.get("alertRule", essentials.get("title", "Azure alert")),
        "severity":   essentials.get("severity", "unknown"),
        "monitor_condition": essentials.get("monitorCondition", "Fired"),
        "target":     essentials.get("targetResourceName", ""),
        "fired_at":   essentials.get("firedDateTime", datetime.utcnow().isoformat()),
    }
    _queue_event("azure", event)
    return jsonify({"status": "queued"}), 200


@webhooks_bp.route("/webhooks/kibana", methods=["POST"])
def kibana_webhook():
    """Receive Kibana Alerting webhook notifications."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    event = {
        "title":     data.get("rule", {}).get("name", data.get("title", "Kibana alert")),
        "rule_id":   data.get("rule", {}).get("id", ""),
        "status":    data.get("status", "active"),
        "context":   data.get("context", {}),
    }
    _queue_event("kibana", event)
    return jsonify({"status": "queued"}), 200


@webhooks_bp.route("/webhooks/events", methods=["GET"])
def get_events():
    """Return recent webhook events for monitoring."""
    with _event_lock:
        recent = list(reversed(_event_queue[-50:]))
    return jsonify({"events": recent, "total": len(_event_queue)})


@webhooks_bp.route("/webhooks/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "queued_events": len(_event_queue), "endpoints": ["/webhooks/dynatrace", "/webhooks/azure", "/webhooks/kibana"]})


def get_mock_webhook_events() -> dict:
    """Return mock recent webhook events for the dashboard."""
    now = datetime.utcnow()
    from datetime import timedelta
    return {
        "recent_events": [
            {"id": "EVT-00001", "source": "dynatrace", "received": (now - timedelta(minutes=23)).isoformat(), "title": "High failure rate on payment-gateway /v2/transfers", "severity": "critical", "processed": True},
            {"id": "EVT-00002", "source": "azure",     "received": (now - timedelta(minutes=18)).isoformat(), "title": "AKS node payment-gw-node-04 NotReady",              "severity": "high",     "processed": True},
            {"id": "EVT-00003", "source": "kibana",    "received": (now - timedelta(minutes=8)).isoformat(),  "title": "PAN detected in payment-gateway debug log",          "severity": "critical", "processed": True},
            {"id": "EVT-00004", "source": "kibana",    "received": (now - timedelta(minutes=5)).isoformat(),  "title": "Payment Error Rate > 2% rule fired (12 times/hr)",   "severity": "high",     "processed": True},
            {"id": "EVT-00005", "source": "dynatrace", "received": (now - timedelta(minutes=3)).isoformat(),  "title": "fraud-detection CPU saturation (94.2%)",             "severity": "high",     "processed": False},
        ],
        "total_today": 47,
        "avg_response_sec": 1.8,
    }
