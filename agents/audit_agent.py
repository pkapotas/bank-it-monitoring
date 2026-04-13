"""Audit Log & Compliance Agent — tracks privileged access, data access, and compliance violations."""
import json
from datetime import datetime
import anthropic
from config import config
from tools.audit_tools import AUDIT_TOOLS, execute_audit_tool
from models.alerts import AgentReport

AUDIT_SYSTEM_PROMPT = """You are a senior IT Audit and Compliance Engineer at a major commercial bank.
Your responsibilities cover PCI-DSS, SOX, GDPR, and internal policy compliance.

Your investigation strategy:
1. Check for active compliance violations first (audit_get_compliance_violations)
2. Review privileged access events for suspicious activity (audit_get_privileged_access_log)
3. Audit data access for bulk PII/PAN access outside normal patterns (audit_get_data_access_log)
4. Check configuration changes for unapproved modifications (audit_get_config_changes)
5. Review failed authentication campaigns (audit_get_failed_auth_summary)
6. Check Key Vault access for unauthorized secret reads (audit_get_key_vault_access)

Report format:
- COMPLIANCE VIOLATIONS (with mandatory notification deadlines)
- SUSPICIOUS ACCESS PATTERNS
- CONFIGURATION CHANGE RISKS
- REGULATORY EXPOSURE ASSESSMENT
- NUMBERED IMMEDIATE ACTIONS

Be precise. Include evidence, user IDs, timestamps, and regulatory citation."""


def run_audit_agent(lookback_hours: int = 24) -> AgentReport:
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    messages = [{"role": "user", "content": f"Perform a full audit and compliance review for the past {lookback_hours} hours. Focus on PCI-DSS, GDPR, and SOX violations, suspicious access patterns, and unapproved changes."}]
    print(f"  [Audit Agent] Starting investigation (last {lookback_hours}h)...")
    while True:
        response = client.messages.create(model=config.model, max_tokens=8096, thinking={"type": "adaptive"}, system=AUDIT_SYSTEM_PROMPT, tools=AUDIT_TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason in ("end_turn",):
            break
        if response.stop_reason != "tool_use":
            break
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_json = execute_audit_tool(block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_json})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
    final_text = "".join(block.text for block in response.content if hasattr(block, "text"))
    print("  [Audit Agent] Investigation complete.")
    return AgentReport(agent_name="AuditAgent", platform="Audit/Compliance", generated_at=datetime.utcnow(), raw_findings=final_text)
