"""
Configuration for the Bank IT Operations Monitoring System.
Load all secrets from environment variables — never hardcode credentials.
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
class MonitoringConfig:
    # Time window for monitoring queries (minutes)
    lookback_minutes: int = int(os.getenv("MONITORING_LOOKBACK_MINUTES", "60"))
    # Alert severity thresholds
    critical_error_rate_threshold: float = float(os.getenv("CRITICAL_ERROR_RATE", "5.0"))
    warning_error_rate_threshold: float = float(os.getenv("WARNING_ERROR_RATE", "2.0"))
    critical_response_time_ms: int = int(os.getenv("CRITICAL_RESPONSE_MS", "3000"))
    warning_response_time_ms: int = int(os.getenv("WARNING_RESPONSE_MS", "1000"))
    # Banking-specific services to monitor
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
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)


# Singleton config instance
config = AppConfig()
