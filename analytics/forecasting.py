"""
Capacity Forecasting via Linear Regression.

Projects when services will breach SLA thresholds based on current trends.
Uses the last 12 data points (60 minutes at 5-min intervals) to fit
a simple linear model and extrapolate forward.
"""
import random
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Linear regression (pure Python, no numpy required for basic version)
# ---------------------------------------------------------------------------

def _linear_regression(x: list[float], y: list[float]) -> tuple[float, float]:
    """Return (slope, intercept) for the least-squares line through (x, y)."""
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0
    sum_x  = sum(x)
    sum_y  = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi ** 2 for xi in x)
    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0, sum_y / n
    slope     = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def hours_to_breach(
    time_series: list[float],
    threshold: float,
    interval_minutes: int = 5,
) -> float | None:
    """
    Given a time series of metric values (most recent last),
    predict how many hours until the metric reaches threshold.
    Returns None if the trend is flat or declining.
    """
    if not time_series or threshold <= 0:
        return None
    x = list(range(len(time_series)))
    slope, intercept = _linear_regression(x, time_series)
    if slope <= 0:
        return None  # Not trending upward
    current = time_series[-1]
    if current >= threshold:
        return 0.0
    steps_needed = (threshold - intercept) / slope
    steps_remaining = steps_needed - (len(time_series) - 1)
    if steps_remaining <= 0:
        return 0.0
    hours = (steps_remaining * interval_minutes) / 60
    return round(hours, 2)


def forecast_value(time_series: list[float], steps_ahead: int) -> float:
    """Project the metric value `steps_ahead` intervals into the future."""
    x = list(range(len(time_series)))
    slope, intercept = _linear_regression(x, time_series)
    future_x = len(time_series) - 1 + steps_ahead
    return round(intercept + slope * future_x, 2)


# ---------------------------------------------------------------------------
# Mock time-series generators (replace with real TSDB queries)
# ---------------------------------------------------------------------------

def _generate_trend(start: float, end: float, n: int = 12, noise: float = 0.05) -> list[float]:
    """Generate a noisy linear trend from start to end over n points."""
    pts = []
    for i in range(n):
        base = start + (end - start) * (i / max(n - 1, 1))
        jitter = base * random.uniform(-noise, noise)
        pts.append(round(base + jitter, 2))
    return pts


def get_mock_forecasts() -> dict:
    """Return capacity forecasts for all critical services."""
    now = datetime.utcnow()
    labels = [(now - timedelta(minutes=55 - i * 5)).strftime("%H:%M") for i in range(12)]

    forecasts = [
        {
            "service":      "fraud-detection",
            "metric":       "cpu_pct",
            "unit":         "%",
            "threshold":    90.0,
            "threshold_label": "CPU critical threshold",
            "trend":        _generate_trend(71, 94.2, noise=0.03),
            "hours_to_breach": 2.4,
            "forecast_4h":  round(94.2 + 4 * 3.1, 1),   # extrapolated
            "trend_direction": "increasing",
            "severity":     "high",
            "recommendation": "Schedule ML training job outside business hours; add 2 nodes to fraud-ml pool",
        },
        {
            "service":      "payment-gateway",
            "metric":       "error_rate",
            "unit":         "%",
            "threshold":    5.0,
            "threshold_label": "SLO critical threshold",
            "trend":        _generate_trend(0.4, 4.7, noise=0.08),
            "hours_to_breach": 0.0,
            "forecast_4h":  round(4.7 + 4 * 0.5, 2),
            "trend_direction": "increasing",
            "severity":     "critical",
            "recommendation": "Already breached. Failover to secondary clearing-house provider immediately.",
        },
        {
            "service":      "core-banking-api",
            "metric":       "p90_ms",
            "unit":         "ms",
            "threshold":    2000.0,
            "threshold_label": "SLA p90 threshold",
            "trend":        _generate_trend(820, 1850, noise=0.04),
            "hours_to_breach": 0.0,
            "forecast_4h":  round(1850 + 4 * 120, 0),
            "trend_direction": "increasing",
            "severity":     "critical",
            "recommendation": "Already breached. Add missing index on ACCOUNTS table; scale DB vertically.",
        },
        {
            "service":      "atm-network",
            "metric":       "error_rate",
            "unit":         "%",
            "threshold":    3.0,
            "threshold_label": "SLO warning threshold",
            "trend":        _generate_trend(0.6, 2.1, noise=0.06),
            "hours_to_breach": 1.8,
            "forecast_4h":  round(2.1 + 4 * 0.22, 2),
            "trend_direction": "increasing",
            "severity":     "high",
            "recommendation": "Investigate disk I/O on atm-gateway-02; preemptively expand disk capacity.",
        },
        {
            "service":      "redis-session",
            "metric":       "connection_pool_pct",
            "unit":         "%",
            "threshold":    95.0,
            "threshold_label": "Pool exhaustion threshold",
            "trend":        _generate_trend(75, 91, noise=0.02),
            "hours_to_breach": 3.2,
            "forecast_4h":  round(91 + 4 * 1.8, 1),
            "trend_direction": "increasing",
            "severity":     "medium",
            "recommendation": "Increase Redis max connections to 500; investigate connection leaks in core-banking-api.",
        },
        {
            "service":      "core-banking-sqlserver",
            "metric":       "dtu_pct",
            "unit":         "%",
            "threshold":    90.0,
            "threshold_label": "DTU critical threshold",
            "trend":        _generate_trend(62, 87, noise=0.03),
            "hours_to_breach": 1.2,
            "forecast_4h":  round(87 + 4 * 2.5, 1),
            "trend_direction": "increasing",
            "severity":     "high",
            "recommendation": "Scale Azure SQL to Premium P4; optimize top 3 slow queries in the next hour.",
        },
    ]

    # Attach chart labels to each forecast
    for fc in forecasts:
        fc["labels"] = labels

    breaching_now = sum(1 for f in forecasts if f["hours_to_breach"] == 0.0)
    breaching_soon = sum(1 for f in forecasts if 0.0 < f["hours_to_breach"] <= 4.0)

    return {
        "generated_at":   now.isoformat(),
        "forecasts":      forecasts,
        "breaching_now":  breaching_now,
        "breaching_4h":   breaching_soon,
        "total_tracked":  len(forecasts),
    }
