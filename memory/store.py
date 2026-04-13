"""
Incident Memory Store.

Persists MonitoringReports to a JSON file and retrieves similar past
incidents using TF-IDF cosine similarity. No external vector DB required.

In production, replace with ChromaDB, pgvector, or Pinecone for
scalable semantic search.
"""
import json
import math
import os
import re
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# TF-IDF similarity (pure Python)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][-a-z0-9]*", text.lower())


def _tfidf_vector(doc_tokens: list[str], all_docs_tokens: list[list[str]]) -> dict[str, float]:
    n = len(all_docs_tokens)
    tf: dict[str, float] = {}
    for t in doc_tokens:
        tf[t] = tf.get(t, 0) + 1
    total = len(doc_tokens) or 1
    for t in tf:
        tf[t] /= total

    idf: dict[str, float] = {}
    for t in tf:
        df = sum(1 for doc in all_docs_tokens if t in doc)
        idf[t] = math.log((n + 1) / (df + 1)) + 1

    return {t: tf[t] * idf[t] for t in tf}


def _cosine_similarity(v1: dict, v2: dict) -> float:
    common = set(v1) & set(v2)
    dot = sum(v1[t] * v2[t] for t in common)
    mag1 = math.sqrt(sum(x ** 2 for x in v1.values()))
    mag2 = math.sqrt(sum(x ** 2 for x in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return round(dot / (mag1 * mag2), 4)


# ---------------------------------------------------------------------------
# Incident Memory Store
# ---------------------------------------------------------------------------

class IncidentMemoryStore:
    """
    File-backed store for MonitoringReports.
    Each entry is a dict with: id, timestamp, summary_text, overall_status,
    services_affected, alert_ids, raw_findings.
    """

    def __init__(self, store_path: str = "memory/incident_store.json"):
        self.store_path = store_path
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        self._records: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return _get_seed_records()

    def _save(self) -> None:
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2, default=str)

    def save_incident(self, report: dict) -> str:
        """Persist a monitoring report. Returns the generated incident ID."""
        incident_id = f"INC-{len(self._records) + 1:05d}"
        record = {
            "id":               incident_id,
            "timestamp":        report.get("generated_at", datetime.utcnow().isoformat()),
            "overall_status":   report.get("overall_status", "unknown"),
            "escalation":       report.get("escalation_required", False),
            "services_affected": report.get("services_affected", []),
            "alert_count":      report.get("incident_count", 0),
            "summary_text":     report.get("incident_summary", ""),
            "raw_findings":     report.get("raw_findings", ""),
        }
        self._records.append(record)
        self._save()
        return incident_id

    def find_similar(self, query_text: str, top_k: int = 3, min_similarity: float = 0.15) -> list[dict]:
        """Return the top_k most similar past incidents to query_text."""
        if not self._records:
            return []

        # Build corpus
        all_texts = [r.get("summary_text", "") + " " + r.get("raw_findings", "") for r in self._records]
        all_tokens = [_tokenize(t) for t in all_texts]
        query_tokens = _tokenize(query_text)

        if not query_tokens:
            return []

        # Compute query TF-IDF against corpus
        all_tokens_with_query = all_tokens + [query_tokens]
        query_vec = _tfidf_vector(query_tokens, all_tokens_with_query)

        scored = []
        for i, record in enumerate(self._records):
            doc_vec = _tfidf_vector(all_tokens[i], all_tokens_with_query)
            sim = _cosine_similarity(query_vec, doc_vec)
            if sim >= min_similarity:
                scored.append({**record, "similarity": sim})

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    def get_recent(self, n: int = 5) -> list[dict]:
        """Return the n most recent incidents."""
        return list(reversed(self._records[-n:]))

    def count(self) -> int:
        return len(self._records)


# ---------------------------------------------------------------------------
# Seed data -- realistic historical incidents for demo
# ---------------------------------------------------------------------------

def _get_seed_records() -> list[dict]:
    return [
        {
            "id": "INC-00001",
            "timestamp": "2026-03-21T14:23:00",
            "overall_status": "critical",
            "escalation": True,
            "services_affected": ["payment-gateway", "transaction-processor"],
            "alert_count": 4,
            "summary_text": (
                "CRITICAL: payment-gateway experienced 4.9% error rate due to clearing-house certificate rotation. "
                "CircuitBreaker OPEN for 38 minutes. 412 customers affected. EUR 18.2M transactions delayed. "
                "Fix: certificate renewed, gateway restarted. RCA: automated cert rotation missed notification."
            ),
            "raw_findings": "payment-gateway error 4.9% clearing-house certificate expired connection timeout CircuitBreaker OPEN",
        },
        {
            "id": "INC-00002",
            "timestamp": "2026-03-28T03:14:00",
            "overall_status": "critical",
            "escalation": True,
            "services_affected": ["core-banking-api", "core-banking-sqlserver"],
            "alert_count": 3,
            "summary_text": (
                "CRITICAL: core-banking-api p90 degraded to 3200ms (target: 1000ms). "
                "Root cause: schema migration ran without adding index on TRANSACTIONS table. "
                "1840 slow queries/hr. 2,100 users affected. Fix: index added, query cache cleared."
            ),
            "raw_findings": "core-banking-api latency p90 3200ms slow query missing index TRANSACTIONS table schema migration",
        },
        {
            "id": "INC-00003",
            "timestamp": "2026-04-02T19:45:00",
            "overall_status": "critical",
            "escalation": True,
            "services_affected": ["authentication-service"],
            "alert_count": 2,
            "summary_text": (
                "CRITICAL: Credential stuffing attack from 3 Tor exit nodes. "
                "1,240 failed login attempts over 2 hours. 14 accounts locked. "
                "Fix: IP block at WAF, step-up MFA enabled for affected accounts."
            ),
            "raw_findings": "authentication-service credential stuffing brute force Tor exit node failed login MFA",
        },
        {
            "id": "INC-00004",
            "timestamp": "2026-04-05T11:30:00",
            "overall_status": "degraded",
            "escalation": False,
            "services_affected": ["atm-network"],
            "alert_count": 2,
            "summary_text": (
                "HIGH: ATM network availability dropped to 97.1% (SLO: 99.5%). "
                "Root cause: atm-gateway-01 disk I/O saturation during log rotation. "
                "Fix: log rotation rescheduled to 02:00 UTC, disk expanded."
            ),
            "raw_findings": "atm-network availability 97.1% disk IO saturation log rotation gateway",
        },
        {
            "id": "INC-00005",
            "timestamp": "2026-04-08T09:12:00",
            "overall_status": "critical",
            "escalation": True,
            "services_affected": ["payment-gateway", "fraud-detection"],
            "alert_count": 5,
            "summary_text": (
                "CRITICAL: PCI-DSS violation detected. PAN data in payment-gateway application log. "
                "Simultaneously, fraud-detection CPU saturation (91%) during model re-training. "
                "Compliance: PCI incident report filed. Training job moved to maintenance window."
            ),
            "raw_findings": "PCI-DSS PAN primary account number payment-gateway debug log fraud-detection CPU saturation model training",
        },
        {
            "id": "INC-00006",
            "timestamp": "2026-04-10T16:55:00",
            "overall_status": "degraded",
            "escalation": False,
            "services_affected": ["swift-connector"],
            "alert_count": 1,
            "summary_text": (
                "HIGH: SWIFT connector missed SLA for 2 MT103 messages (processing > 5s). "
                "Root cause: upstream SWIFT SWIFTNet link momentary congestion. "
                "Both messages processed successfully on retry. No financial impact."
            ),
            "raw_findings": "swift-connector MT103 SLA breach SWIFTNet congestion retry",
        },
    ]


# Singleton store instance
_store: Optional[IncidentMemoryStore] = None


def get_store() -> IncidentMemoryStore:
    global _store
    if _store is None:
        from config import config
        _store = IncidentMemoryStore(config.memory_store_path)
    return _store


def get_mock_memory_context(query: str = "") -> dict:
    """Return similar past incidents for dashboard display."""
    store = get_store()
    if not query:
        query = (
            "payment-gateway error rate clearing-house timeout CircuitBreaker "
            "credential stuffing PCI-DSS violation core-banking latency"
        )
    similar = store.find_similar(query, top_k=3)
    return {
        "query_summary": "Current incident pattern",
        "total_incidents_in_memory": store.count(),
        "similar_incidents": similar,
    }
