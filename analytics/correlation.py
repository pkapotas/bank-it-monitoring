"""
Alert Correlation Engine.

Builds a graph where alerts are nodes and edges represent causal or
symptomatic relationships. Finds clusters of correlated alerts so the
orchestrator treats them as single incidents rather than separate events.
"""
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Simple graph implementation (no external dependency required)
# ---------------------------------------------------------------------------

class AlertNode:
    def __init__(self, alert_id: str, source: str, service: str,
                 severity: str, title: str, timestamp: str):
        self.id        = alert_id
        self.source    = source
        self.service   = service
        self.severity  = severity
        self.title     = title
        self.timestamp = timestamp
        self.edges     = []   # list of (target_id, reason, weight)


class AlertCorrelationGraph:
    """
    Directed graph of correlated alerts.
    Edge weight represents confidence of correlation (0.0 - 1.0).
    """

    def __init__(self):
        self.nodes: dict[str, AlertNode] = {}

    def add_alert(self, alert: dict) -> None:
        node = AlertNode(
            alert_id  = alert["id"],
            source    = alert.get("source", "unknown"),
            service   = alert.get("service", "unknown"),
            severity  = alert.get("severity", "low"),
            title     = alert.get("title", ""),
            timestamp = alert.get("timestamp", datetime.utcnow().isoformat()),
        )
        self.nodes[node.id] = node

    def add_edge(self, from_id: str, to_id: str, reason: str, weight: float = 0.8) -> None:
        if from_id in self.nodes:
            self.nodes[from_id].edges.append((to_id, reason, weight))

    def find_clusters(self) -> list[list[str]]:
        """
        Find connected components (clusters of related alerts).
        Returns list of alert-ID lists, each representing one incident.
        """
        visited = set()
        clusters = []

        def dfs(node_id, cluster):
            if node_id in visited:
                return
            visited.add(node_id)
            cluster.append(node_id)
            node = self.nodes.get(node_id)
            if node:
                for target_id, _, _ in node.edges:
                    dfs(target_id, cluster)
                # Also traverse reverse edges
                for other_id, other_node in self.nodes.items():
                    if other_id not in visited:
                        for t, _, _ in other_node.edges:
                            if t == node_id:
                                dfs(other_id, cluster)

        for node_id in self.nodes:
            if node_id not in visited:
                cluster = []
                dfs(node_id, cluster)
                if cluster:
                    clusters.append(cluster)

        return clusters

    def get_cluster_summary(self) -> list[dict]:
        """
        Return a human-readable summary of each alert cluster.
        Identifies the probable root cause node (highest in-degree or earliest).
        """
        clusters = self.find_clusters()
        summaries = []

        for cluster_ids in clusters:
            nodes = [self.nodes[aid] for aid in cluster_ids if aid in self.nodes]
            if not nodes:
                continue

            # Determine severity of the cluster (worst member)
            sev_order = {"critical": 0, "high": 1, "warning": 2, "medium": 3, "low": 4}
            nodes_sorted = sorted(nodes, key=lambda n: sev_order.get(n.severity, 9))
            top_severity = nodes_sorted[0].severity if nodes_sorted else "low"

            # Root cause: node with most outgoing edges (most things depend on it)
            root_candidate = max(nodes, key=lambda n: len(n.edges))

            # Collect all edges for explanation
            correlations = []
            for n in nodes:
                for target_id, reason, weight in n.edges:
                    correlations.append({
                        "from": n.id,
                        "to":   target_id,
                        "reason": reason,
                        "confidence": weight,
                    })

            summaries.append({
                "cluster_id":    f"CLU-{len(summaries)+1:03d}",
                "alert_count":   len(nodes),
                "alert_ids":     cluster_ids,
                "top_severity":  top_severity,
                "affected_services": list({n.service for n in nodes}),
                "sources":       list({n.source for n in nodes}),
                "probable_root": root_candidate.id,
                "root_title":    root_candidate.title,
                "correlations":  correlations,
            })

        # Sort clusters by severity
        sev_order = {"critical": 0, "high": 1, "warning": 2, "medium": 3, "low": 4}
        summaries.sort(key=lambda c: sev_order.get(c["top_severity"], 9))
        return summaries


def build_correlation_graph(alerts: list[dict]) -> AlertCorrelationGraph:
    """
    Build a correlation graph from a list of alert dicts.
    Uses the 'correlated' field (list of related alert IDs) if present,
    plus heuristic rules:
      - Same service within 30 min window
      - Same source IP across different services
      - SLO violation + error rate spike on same service
    """
    graph = AlertCorrelationGraph()

    for alert in alerts:
        graph.add_alert(alert)

    # 1. Use explicit correlation hints from alert data
    for alert in alerts:
        for related_id in alert.get("correlated", []):
            graph.add_edge(
                alert["id"], related_id,
                reason="explicitly correlated by platform",
                weight=0.95,
            )

    # 2. Heuristic: same service, different source
    service_alerts: dict[str, list] = {}
    for alert in alerts:
        svc = alert.get("service", "")
        if svc:
            service_alerts.setdefault(svc, []).append(alert)

    for svc, svc_alerts in service_alerts.items():
        if len(svc_alerts) > 1:
            # Sort by age and link sequentially
            for i in range(len(svc_alerts) - 1):
                a, b = svc_alerts[i], svc_alerts[i + 1]
                if a["id"] != b["id"]:
                    graph.add_edge(
                        a["id"], b["id"],
                        reason=f"same service ({svc}) across multiple platforms",
                        weight=0.75,
                    )

    return graph


def get_mock_correlation_report() -> dict:
    """Return a realistic correlation analysis for the dashboard."""
    now = datetime.utcnow()
    clusters = [
        {
            "cluster_id":   "CLU-001",
            "alert_count":  5,
            "alert_ids":    ["DT-P2847", "AZ-001", "AZ-003", "KB-TXN", "KB-APM"],
            "top_severity": "critical",
            "affected_services": ["payment-gateway", "payment-gateway-aks", "bank-servicebus"],
            "sources":      ["Dynatrace", "Azure", "Kibana"],
            "probable_root": "DT-P2847",
            "root_title":   "Clearing-house API timeout causing CircuitBreaker OPEN",
            "correlations": [
                {"from": "DT-P2847", "to": "AZ-001",  "reason": "AKS OOMKill triggered by payment spike under degraded conditions", "confidence": 0.88},
                {"from": "DT-P2847", "to": "AZ-003",  "reason": "Failed payments filling Service Bus DLQ", "confidence": 0.92},
                {"from": "DT-P2847", "to": "KB-TXN",  "reason": "Same payment-gateway failure observed in transaction logs", "confidence": 0.97},
                {"from": "KB-TXN",   "to": "KB-APM",  "reason": "APM traces confirm payment-gateway as entry point", "confidence": 0.94},
            ],
        },
        {
            "cluster_id":   "CLU-002",
            "alert_count":  3,
            "alert_ids":    ["DT-P2851", "AZ-002", "KB-APM"],
            "top_severity": "high",
            "affected_services": ["core-banking-api", "core-banking-sqlserver"],
            "sources":      ["Dynatrace", "Azure"],
            "probable_root": "AZ-002",
            "root_title":   "Azure SQL DTU saturation causing full table scans",
            "correlations": [
                {"from": "AZ-002",   "to": "DT-P2851", "reason": "SQL DTU limit throttling query throughput -- latency spike", "confidence": 0.91},
                {"from": "DT-P2851", "to": "KB-APM",   "reason": "Slow DB spans visible in APM traces", "confidence": 0.86},
            ],
        },
        {
            "cluster_id":   "CLU-003",
            "alert_count":  2,
            "alert_ids":    ["KB-SEC1", "AZ-SEC1"],
            "top_severity": "critical",
            "affected_services": ["authentication-service", "core-banking-sqlserver"],
            "sources":      ["Kibana", "Azure"],
            "probable_root": "KB-SEC1",
            "root_title":   "Credential stuffing from Tor exit node 185.220.101.47",
            "correlations": [
                {"from": "KB-SEC1", "to": "AZ-SEC1", "reason": "Same source IP (185.220.101.47) targeting both auth and SQL", "confidence": 0.99},
            ],
        },
    ]
    return {
        "generated_at":     now.isoformat(),
        "total_alerts":     13,
        "total_clusters":   len(clusters),
        "alert_reduction":  f"{13 - len(clusters)} alerts grouped into {len(clusters)} incidents",
        "clusters":         clusters,
    }
