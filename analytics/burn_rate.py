"""
Multi-Window SLO Burn Rate Alerting (Google SRE Golden Standard).

An SLO burn rate alert fires when:
  - 1h window:  burn_rate > 14x  (fast burn -- page immediately)
  - 6h window:  burn_rate > 3x   (slow burn -- ticket urgently)
  - BOTH windows must be elevated to reduce false positives

Burn rate = (error rate observed) / (error rate budget)
Example: SLO 99.9% = 0.1% error budget. If observing 1.4% errors,
         burn_rate = 1.4% / 0.1% = 14x

Error budget consumed = burn_rate x (observation window / SLO window)
"""
from datetime import datetime, timedelta
import random


def compute_burn_rate(current_error_pct: float, slo_target_pct: float) -> float:
    """
    Compute current burn rate.
    slo_target_pct: e.g. 99.9 means 0.1% error budget
    current_error_pct: observed error percentage
    """
    error_budget_pct = 100.0 - slo_target_pct
    if error_budget_pct <= 0:
        return 0.0
    return round(current_error_pct / error_budget_pct, 2)


def budget_consumed_pct(burn_rate: float, window_hours: float, slo_period_days: int = 30) -> float:
    """
    Estimate percentage of monthly error budget consumed at current burn rate
    over the observation window.
    """
    slo_period_hours = slo_period_days * 24
    return round((burn_rate * window_hours / slo_period_hours) * 100, 2)


def evaluate_slo(slo: dict) -> dict:
    """
    Run multi-window burn rate evaluation for a single SLO.
    slo must have: id, name, target (e.g. 99.9), current (e.g. 98.2)
    """
    target     = slo["target"]
    current    = slo["current"]
    error_budget = 100.0 - target
    current_error = 100.0 - current

    # Fast window (1h): simulated as current conditions
    br_fast = compute_burn_rate(current_error, target)
    # Slow window (6h): slightly lower (conditions may have been better before)
    br_slow = compute_burn_rate(current_error * random.uniform(0.6, 0.9), target)

    # Budget consumed
    consumed_1h  = budget_consumed_pct(br_fast, 1)
    consumed_6h  = budget_consumed_pct(br_slow, 6)
    consumed_24h = budget_consumed_pct(br_slow, 24)

    # Determine alert tier
    # Tier 1 (PAGE NOW): fast burn > 14x AND slow burn > 3x
    # Tier 2 (TICKET):   fast burn > 6x  OR  slow burn > 1x
    if br_fast >= 14.0 and br_slow >= 3.0:
        alert_tier = "page"
        alert_label = "PAGE NOW"
        alert_color = "critical"
    elif br_fast >= 6.0 or br_slow >= 1.0:
        alert_tier = "ticket"
        alert_label = "TICKET URGENTLY"
        alert_color = "high"
    elif br_fast >= 1.0:
        alert_tier = "watch"
        alert_label = "WATCH"
        alert_color = "warning"
    else:
        alert_tier = "ok"
        alert_label = "OK"
        alert_color = "healthy"

    # Time to exhaustion at current burn rate
    remaining_budget_pct = max(0.0, current - (target - error_budget)) / error_budget * 100
    if br_fast > 0:
        hours_to_exhaustion = round((remaining_budget_pct / 100 * 30 * 24) / br_fast, 1)
    else:
        hours_to_exhaustion = None

    return {
        "slo_id":               slo["id"],
        "slo_name":             slo["name"],
        "target":               target,
        "current":              current,
        "error_budget_pct":     error_budget,
        "current_error_pct":    round(current_error, 4),
        "burn_rate_1h":         br_fast,
        "burn_rate_6h":         br_slow,
        "budget_consumed_1h":   consumed_1h,
        "budget_consumed_6h":   consumed_6h,
        "budget_consumed_24h":  consumed_24h,
        "alert_tier":           alert_tier,
        "alert_label":          alert_label,
        "alert_color":          alert_color,
        "hours_to_exhaustion":  hours_to_exhaustion,
    }


def get_mock_burn_rate_report() -> dict:
    """Return a full multi-window burn rate report for the dashboard."""
    now = datetime.utcnow()

    slos = [
        {"id": "SLO-001", "name": "Payment Gateway Availability",   "target": 99.9,  "current": 98.2},
        {"id": "SLO-002", "name": "Core Banking p95 < 2s",          "target": 95.0,  "current": 91.3},
        {"id": "SLO-003", "name": "Auth Service Availability",       "target": 99.99, "current": 99.99},
        {"id": "SLO-004", "name": "Fraud Detection p99 < 500ms",     "target": 99.0,  "current": 99.7},
        {"id": "SLO-005", "name": "ATM Network Availability",         "target": 99.5,  "current": 97.8},
    ]

    evaluations = [evaluate_slo(s) for s in slos]

    # Historical burn rate chart data (last 12 x 5min intervals)
    def _burn_history(current_br, noise=0.15):
        pts = []
        for i in range(12):
            v = current_br * (0.3 + 0.7 * (i / 11)) * (1 + random.uniform(-noise, noise))
            pts.append(round(max(0, v), 2))
        return pts

    for ev in evaluations:
        ev["burn_rate_history"] = _burn_history(ev["burn_rate_1h"])

    labels = [(now - timedelta(minutes=55 - i * 5)).strftime("%H:%M") for i in range(12)]

    return {
        "generated_at":  now.isoformat(),
        "labels":        labels,
        "evaluations":   evaluations,
        "summary": {
            "page":   sum(1 for e in evaluations if e["alert_tier"] == "page"),
            "ticket": sum(1 for e in evaluations if e["alert_tier"] == "ticket"),
            "watch":  sum(1 for e in evaluations if e["alert_tier"] == "watch"),
            "ok":     sum(1 for e in evaluations if e["alert_tier"] == "ok"),
        },
    }
