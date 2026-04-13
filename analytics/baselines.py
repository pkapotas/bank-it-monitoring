"""
Anomaly Detection via Rolling Baselines.

Computes 7-day rolling P95 baselines per service/metric and detects
anomalies using z-score deviation. Context-aware: a 4.7% error rate
on payment-gateway is critical; on a batch service it may be normal.
"""
import json
import math
import random
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Simulated historical baseline data (replace with real time-series DB reads)
# ---------------------------------------------------------------------------

# Per-service historical profiles: (mean, std_dev) for each metric
# In production, compute these from 7-day rolling windows in your TSDB.
_HISTORICAL_PROFILES = {
    "payment-gateway": {
        "error_rate":    {"mean": 0.35, "std": 0.12, "p95": 0.62},
        "p90_ms":        {"mean": 520,  "std": 45,   "p95": 600},
        "p99_ms":        {"mean": 1100, "std": 120,  "p95": 1320},
        "cpu_pct":       {"mean": 58,   "std": 8,    "p95": 72},
        "throughput":    {"mean": 1820, "std": 95,   "p95": 1970},
    },
    "core-banking-api": {
        "error_rate":    {"mean": 0.12, "std": 0.04, "p95": 0.19},
        "p90_ms":        {"mean": 820,  "std": 60,   "p95": 920},
        "p99_ms":        {"mean": 1600, "std": 130,  "p95": 1800},
        "cpu_pct":       {"mean": 55,   "std": 7,    "p95": 67},
        "throughput":    {"mean": 3050, "std": 180,  "p95": 3320},
    },
    "fraud-detection": {
        "error_rate":    {"mean": 0.06, "std": 0.02, "p95": 0.10},
        "p90_ms":        {"mean": 88,   "std": 6,    "p95": 98},
        "p99_ms":        {"mean": 195,  "std": 12,   "p95": 215},
        "cpu_pct":       {"mean": 71,   "std": 9,    "p95": 86},
        "throughput":    {"mean": 9600, "std": 320,  "p95": 10100},
    },
    "authentication-service": {
        "error_rate":    {"mean": 0.02, "std": 0.01, "p95": 0.04},
        "p90_ms":        {"mean": 58,   "std": 5,    "p95": 66},
        "p99_ms":        {"mean": 112,  "std": 8,    "p95": 125},
        "cpu_pct":       {"mean": 38,   "std": 5,    "p95": 46},
        "throughput":    {"mean": 14100,"std": 420,  "p95": 14780},
    },
    "transaction-processor": {
        "error_rate":    {"mean": 0.22, "std": 0.06, "p95": 0.33},
        "p90_ms":        {"mean": 680,  "std": 40,   "p95": 746},
        "p99_ms":        {"mean": 1550, "std": 90,   "p95": 1700},
        "cpu_pct":       {"mean": 62,   "std": 8,    "p95": 75},
        "throughput":    {"mean": 2400, "std": 110,  "p95": 2580},
    },
    "account-management": {
        "error_rate":    {"mean": 0.10, "std": 0.03, "p95": 0.15},
        "p90_ms":        {"mean": 430,  "std": 35,   "p95": 488},
        "p99_ms":        {"mean": 920,  "std": 60,   "p95": 1020},
        "cpu_pct":       {"mean": 44,   "std": 6,    "p95": 54},
        "throughput":    {"mean": 5500, "std": 250,  "p95": 5900},
    },
    "swift-connector": {
        "error_rate":    {"mean": 0.15, "std": 0.05, "p95": 0.23},
        "p90_ms":        {"mean": 1100, "std": 80,   "p95": 1230},
        "p99_ms":        {"mean": 2600, "std": 150,  "p95": 2850},
        "cpu_pct":       {"mean": 35,   "std": 5,    "p95": 43},
        "throughput":    {"mean": 330,  "std": 20,   "p95": 363},
    },
    "atm-network": {
        "error_rate":    {"mean": 0.55, "std": 0.12, "p95": 0.75},
        "p90_ms":        {"mean": 1600, "std": 120,  "p95": 1800},
        "p99_ms":        {"mean": 3800, "std": 280,  "p95": 4260},
        "cpu_pct":       {"mean": 48,   "std": 7,    "p95": 59},
        "throughput":    {"mean": 800,  "std": 45,   "p95": 874},
    },
}

_DEFAULT_PROFILE = {
    "error_rate":    {"mean": 0.5,  "std": 0.2,  "p95": 0.9},
    "p90_ms":        {"mean": 500,  "std": 80,   "p95": 630},
    "p99_ms":        {"mean": 1200, "std": 150,  "p95": 1450},
    "cpu_pct":       {"mean": 50,   "std": 10,   "p95": 66},
    "throughput":    {"mean": 1000, "std": 100,  "p95": 1160},
}


def _zscore(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0
    return (value - mean) / std


def get_baseline(service: str, metric: str) -> dict:
    """Return the historical baseline profile for a service/metric."""
    profile = _HISTORICAL_PROFILES.get(service, _DEFAULT_PROFILE)
    return profile.get(metric, {"mean": 0, "std": 1, "p95": 0})


def compute_zscore(service: str, metric: str, current_value: float) -> float:
    """Compute the z-score of current_value against historical baseline."""
    baseline = get_baseline(service, metric)
    return round(_zscore(current_value, baseline["mean"], baseline["std"]), 2)


def is_anomaly(service: str, metric: str, value: float, threshold: float = 2.5) -> bool:
    """Return True if value deviates more than threshold standard deviations from the mean."""
    return abs(compute_zscore(service, metric, value)) >= threshold


def get_anomalies(services_data: list, zscore_threshold: float = 2.5) -> list:
    """
    Scan a list of service health dicts for anomalous metrics.
    Each item in services_data should have: name, error_rate, p90_ms, p99_ms.

    Returns list of anomaly dicts with zscore, baseline, and severity.
    """
    anomalies = []
    for svc in services_data:
        name = svc.get("name", "unknown")
        checks = [
            ("error_rate", svc.get("error_rate", 0)),
            ("p90_ms",     svc.get("p90_ms", 0)),
            ("p99_ms",     svc.get("p99_ms", 0)),
        ]
        for metric, value in checks:
            z = compute_zscore(name, metric, value)
            baseline = get_baseline(name, metric)
            if abs(z) >= zscore_threshold:
                direction = "elevated" if z > 0 else "depressed"
                severity = "critical" if abs(z) >= 4 else ("high" if abs(z) >= 3 else "medium")
                anomalies.append({
                    "service":    name,
                    "metric":     metric,
                    "current":    value,
                    "baseline_mean": baseline["mean"],
                    "baseline_p95":  baseline["p95"],
                    "zscore":     z,
                    "direction":  direction,
                    "severity":   severity,
                    "description": (
                        f"{name} {metric} is {direction} ({value} vs baseline mean "
                        f"{baseline['mean']}, z={z:.1f})"
                    ),
                })
    return sorted(anomalies, key=lambda x: abs(x["zscore"]), reverse=True)


def get_mock_anomaly_report() -> dict:
    """Return a realistic anomaly detection snapshot for the dashboard."""
    now = datetime.utcnow()
    anomalies = [
        {
            "service":       "payment-gateway",
            "metric":        "error_rate",
            "current":       4.70,
            "baseline_mean": 0.35,
            "baseline_p95":  0.62,
            "zscore":        36.2,
            "direction":     "elevated",
            "severity":      "critical",
            "description":   "payment-gateway error_rate 13x above 7-day baseline (4.70% vs 0.35% mean)",
            "first_detected": (now - timedelta(minutes=23)).isoformat(),
        },
        {
            "service":       "atm-network",
            "metric":        "error_rate",
            "current":       2.10,
            "baseline_mean": 0.55,
            "baseline_p95":  0.75,
            "zscore":        12.9,
            "direction":     "elevated",
            "severity":      "critical",
            "description":   "atm-network error_rate 3.8x above 7-day baseline (2.10% vs 0.55% mean)",
            "first_detected": (now - timedelta(minutes=45)).isoformat(),
        },
        {
            "service":       "core-banking-api",
            "metric":        "p90_ms",
            "current":       1850,
            "baseline_mean": 820,
            "baseline_p95":  920,
            "zscore":        17.2,
            "direction":     "elevated",
            "severity":      "critical",
            "description":   "core-banking-api p90 latency 2.3x above 7-day baseline (1850ms vs 820ms mean)",
            "first_detected": (now - timedelta(minutes=8)).isoformat(),
        },
        {
            "service":       "fraud-detection",
            "metric":        "cpu_pct",
            "current":       94.2,
            "baseline_mean": 71,
            "baseline_p95":  86,
            "zscore":        2.6,
            "direction":     "elevated",
            "severity":      "medium",
            "description":   "fraud-detection CPU 2.6 sigma above baseline (94.2% vs 71% mean)",
            "first_detected": (now - timedelta(minutes=45)).isoformat(),
        },
    ]
    return {
        "generated_at": now.isoformat(),
        "total_anomalies": len(anomalies),
        "by_severity": {
            "critical": sum(1 for a in anomalies if a["severity"] == "critical"),
            "high":     sum(1 for a in anomalies if a["severity"] == "high"),
            "medium":   sum(1 for a in anomalies if a["severity"] == "medium"),
        },
        "anomalies": anomalies,
        "baseline_window_days": 7,
        "zscore_threshold": 2.5,
    }
