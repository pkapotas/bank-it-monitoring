"""Shared data models for monitoring alerts and reports."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


@dataclass
class Alert:
    id: str
    source: str          # "dynatrace" | "azure" | "kibana"
    severity: Severity
    title: str
    description: str
    service: str
    timestamp: datetime
    status: AlertStatus = AlertStatus.OPEN
    impact: str = ""
    runbook_url: str = ""
    tags: list = field(default_factory=list)


@dataclass
class ServiceHealth:
    name: str
    status: str          # "healthy" | "degraded" | "down" | "unknown"
    error_rate: float    # percentage
    response_time_ms: float
    availability: float  # percentage
    active_alerts: int
    last_checked: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentReport:
    agent_name: str
    platform: str
    generated_at: datetime
    alerts: list = field(default_factory=list)
    service_health: list = field(default_factory=list)
    metrics_summary: dict = field(default_factory=dict)
    raw_findings: str = ""
    error: Optional[str] = None


@dataclass
class MonitoringReport:
    generated_at: datetime
    overall_status: str    # "healthy" | "degraded" | "critical" | "unknown"
    dynatrace_report: Optional[AgentReport] = None
    azure_report: Optional[AgentReport] = None
    kibana_report: Optional[AgentReport] = None
    consolidated_alerts: list = field(default_factory=list)
    incident_summary: str = ""
    recommendations: list = field(default_factory=list)
    escalation_required: bool = False
