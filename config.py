"""
Configuration for the Bank IT Operations Monitoring System.
Load all secrets from environment variables -- never hardcode credentials.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DynatraceConfig:
    base_url: str = field(default_factory=lambda: os.getenv("DYNATRACE_BASE_URL", "https://your-tenant.live.dynatrace.com"))
    api_token: str = field(default_factory=lambda: os.getenv("DYNATRACE_API_TOKEN", ""))
    environment_id: str = field(default_factory=lambda: os.getenv("DYNATRACE_ENV_ID", ""))


@dataclass
class AzureConfig:
    tenant_id: str = field(default_factory=lambda: os.getenv("AZURE_TENANT_ID", ""))
    client_id: str = field(default_factory=lambda: os.getenv("AZURE_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("AZURE_CLIENT_SECRET", ""))
    subscription_id: str = field(default_factory=lambda: os.getenv("AZURE_SUBSCRIPTION_ID", ""))
    resource_group: str = field(default_factory=lambda: os.getenv("AZURE_RESOURCE_GROUP", "bank-prod-rg"))
    log_workspace_id: str = field(default_factory=lambda: os.getenv("AZURE_LOG_WORKSPACE_ID", ""))


@dataclass
class KibanaConfig:
    base_url: str = field(default_factory=lambda: os.getenv("KIBANA_BASE_URL", "https://kibana.bank.internal:5601"))
    username: str = field(default_factory=lambda: os.getenv("KIBANA_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("KIBANA_PASSWORD", ""))
    api_key: str = field(default_factory=lambda: os.getenv("KIBANA_API_KEY", ""))
    elasticsearch_url: str = field(default_factory=lambda: os.getenv("ELASTICSEARCH_URL", "https://elasticsearch.bank.internal:9200"))


@dataclass
class PagerDutyConfig:
    api_key: str = field(default_factory=lambda: os.getenv("PAGERDUTY_API_KEY", ""))
    service_id: str = field(default_factory=lambda: os.getenv("PAGERDUTY_SERVICE_ID", "P1234567"))
    escalation_policy_id: str = field(default_factory=lambda: os.getenv("PAGERDUTY_ESCALATION_POLICY", "P7654321"))
    enabled: bool = field(default_factory=lambda: os.getenv("PAGERDUTY_ENABLED", "false").lower() == "true")


@dataclass
class SlackConfig:
    bot_token: str = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN", ""))
    ops_channel: str = field(default_factory=lambda: os.getenv("SLACK_OPS_CHANNEL", "#it-ops-alerts"))
    approval_channel: str = field(default_factory=lambda: os.getenv("SLACK_APPROVAL_CHANNEL", "#runbook-approvals"))
    enabled: bool = field(default_factory=lambda: os.getenv("SLACK_ENABLED", "false").lower() == "true")


@dataclass
class ThreatIntelConfig:
    abuseipdb_key: str = field(default_factory=lambda: os.getenv("ABUSEIPDB_API_KEY", ""))
    virustotal_key: str = field(default_factory=lambda: os.getenv("VIRUSTOTAL_API_KEY", ""))
    enabled: bool = field(default_factory=lambda: os.getenv("THREAT_INTEL_ENABLED", "false").lower() == "true")


@dataclass
class EnvironmentConfig:
    name: str = "prod"
    dynatrace: DynatraceConfig = field(default_factory=DynatraceConfig)
    azure: AzureConfig = field(default_factory=AzureConfig)
    kibana: KibanaConfig = field(default_factory=KibanaConfig)


@dataclass
class MonitoringConfig:
    lookback_minutes: int = int(os.getenv("MONITORING_LOOKBACK_MINUTES", "60"))
    critical_error_rate_threshold: float = float(os.getenv("CRITICAL_ERROR_RATE", "5.0"))
    warning_error_rate_threshold: float = float(os.getenv("WARNING_ERROR_RATE", "2.0"))
    critical_response_time_ms: int = int(os.getenv("CRITICAL_RESPONSE_MS", "3000"))
    warning_response_time_ms: int = int(os.getenv("WARNING_RESPONSE_MS", "1000"))
    # Baseline anomaly detection: z-score threshold
    anomaly_zscore_threshold: float = float(os.getenv("ANOMALY_ZSCORE_THRESHOLD", "2.5"))
    # Burn rate thresholds (Google SRE golden signals)
    burn_rate_fast_threshold: float = float(os.getenv("BURN_RATE_FAST", "14.0"))   # 1h window
    burn_rate_slow_threshold: float = float(os.getenv("BURN_RATE_SLOW", "3.0"))    # 6h window
    # Environments to monitor
    environments: list = field(default_factory=lambda: ["prod", "staging", "dr"])
    # Banking services
    critical_services: list = field(default_factory=lambda: [
        "payment-gateway",
        "core-banking-api",
        "fraud-detection",
        "authentication-service",
        "transaction-processor",
        "account-management",
        "swift-connector",
        "atm-network",
    ])


@dataclass
class AppConfig:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = "claude-opus-4-6"
    dynatrace: DynatraceConfig = field(default_factory=DynatraceConfig)
    azure: AzureConfig = field(default_factory=AzureConfig)
    kibana: KibanaConfig = field(default_factory=KibanaConfig)
    pagerduty: PagerDutyConfig = field(default_factory=PagerDutyConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    threat_intel: ThreatIntelConfig = field(default_factory=ThreatIntelConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    # Memory store path
    memory_store_path: str = field(default_factory=lambda: os.getenv("MEMORY_STORE_PATH", "memory/incident_store.json"))


# Singleton config instance
config = AppConfig()
