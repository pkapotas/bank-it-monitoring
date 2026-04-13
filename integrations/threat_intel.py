"""
Threat Intelligence Feed Integration.
Enriches security alerts with IP reputation data from AbuseIPDB / VirusTotal.
Replace mock with real API calls when THREAT_INTEL_ENABLED=true.
"""
import re
import requests
from datetime import datetime
from config import config

# ---------------------------------------------------------------------------
# Known malicious IPs (seed data for demo)
# ---------------------------------------------------------------------------
_THREAT_DB = {
    "185.220.101.47": {
        "reputation": "malicious", "confidence": 98, "abuse_score": 100,
        "isp": "Tor Project", "country": "Unknown", "asn": "AS205100",
        "categories": ["Tor Exit Node", "Brute Force", "Credential Stuffing"],
        "reports_30d": 847, "first_seen": "2021-03-14",
        "last_seen": "2026-04-13T13:51:00Z",
        "threat_campaigns": ["TA505 credential harvesting", "BEC fraud infrastructure"],
        "virustotal_detections": "38/94 engines flagged",
        "recommendation": "Block at WAF/NSG immediately. Enable step-up MFA for accounts targeted from this IP.",
    },
    "91.108.4.33": {
        "reputation": "suspicious", "confidence": 74, "abuse_score": 62,
        "isp": "Telegram Messenger Inc.", "country": "RU", "asn": "AS62041",
        "categories": ["Password Spray", "Scanning"],
        "reports_30d": 34, "first_seen": "2026-02-01",
        "last_seen": "2026-04-13T13:28:00Z",
        "threat_campaigns": ["Generic password spray"],
        "virustotal_detections": "12/94 engines flagged",
        "recommendation": "Block at perimeter. Flag any successful logins from this IP for account review.",
    },
    "10.0.5.23": {
        "reputation": "internal", "confidence": 0, "abuse_score": 0,
        "isp": "Internal", "country": "Internal", "asn": "Internal",
        "categories": ["Internal Network"],
        "reports_30d": 0,
        "recommendation": "Internal IP -- investigate service account misuse rather than IP blocking.",
    },
    "10.0.2.45": {
        "reputation": "internal", "confidence": 0, "abuse_score": 0,
        "isp": "Internal", "country": "Internal", "asn": "Internal",
        "categories": ["Internal Network -- Developer Workstation"],
        "reports_30d": 0,
        "recommendation": "Internal developer IP -- investigate user activity, not network block.",
    },
}


def enrich_ip(ip_address: str) -> dict:
    """Return threat intelligence for an IP address."""
    if not _is_valid_ip(ip_address):
        return {"error": "Invalid IP address", "ip": ip_address}

    # Check mock DB first (covers demo IPs)
    if ip_address in _THREAT_DB:
        return {"ip": ip_address, "source": "mock_threat_db", **_THREAT_DB[ip_address]}

    # Real API calls if enabled
    if config.threat_intel.enabled:
        result = {}
        if config.threat_intel.abuseipdb_key:
            result = _query_abuseipdb(ip_address)
        return result

    # Unknown IP fallback
    return {
        "ip": ip_address, "reputation": "unknown", "confidence": 0, "abuse_score": 0,
        "isp": "unknown", "country": "unknown", "categories": [],
        "source": "mock", "note": "Set THREAT_INTEL_ENABLED=true and API keys for live enrichment",
    }


def enrich_alerts(alerts: list[dict]) -> list[dict]:
    """Add threat intel enrichment to all alerts that have a source IP."""
    enriched = []
    for alert in alerts:
        a = dict(alert)
        # Extract IP from description if not explicit
        ip = alert.get("source_ip") or _extract_ip(alert.get("description", ""))
        if ip:
            a["threat_intel"] = enrich_ip(ip)
        enriched.append(a)
    return enriched


def get_mock_threat_summary() -> dict:
    """Return enriched threat intel for the dashboard."""
    now = datetime.utcnow()
    ips = [
        {"ip": "185.220.101.47", "context": "Credential stuffing source (87 attempts)", "first_seen_in_env": "42 minutes ago"},
        {"ip": "91.108.4.33",    "context": "Password spray against Azure AD (14 attempts)", "first_seen_in_env": "28 minutes ago"},
        {"ip": "10.0.2.45",      "context": "PCI violation -- debug log with PAN", "first_seen_in_env": "8 minutes ago"},
    ]
    enriched = []
    for item in ips:
        intel = enrich_ip(item["ip"])
        enriched.append({**item, **intel})

    return {
        "generated_at": now.isoformat(),
        "total_ips_analysed": len(enriched),
        "malicious_count": sum(1 for e in enriched if e.get("reputation") == "malicious"),
        "suspicious_count": sum(1 for e in enriched if e.get("reputation") == "suspicious"),
        "enriched_ips": enriched,
    }


def _query_abuseipdb(ip: str) -> dict:
    try:
        resp = requests.get(
            "https://api.abuseipdb.com/api/v2/check",
            headers={"Key": config.threat_intel.abuseipdb_key, "Accept": "application/json"},
            params={"ipAddress": ip, "maxAgeInDays": 90, "verbose": True},
            timeout=10,
        )
        d = resp.json().get("data", {})
        return {
            "ip":          ip,
            "reputation":  "malicious" if d.get("abuseConfidenceScore", 0) >= 75 else "suspicious",
            "confidence":  d.get("abuseConfidenceScore", 0),
            "isp":         d.get("isp", "unknown"),
            "country":     d.get("countryCode", "unknown"),
            "reports_30d": d.get("totalReports", 0),
            "source":      "abuseipdb",
        }
    except Exception as e:
        return {"ip": ip, "reputation": "unknown", "error": str(e), "source": "abuseipdb_error"}


def _is_valid_ip(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def _extract_ip(text: str) -> str | None:
    match = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", text)
    return match.group(1) if match else None
