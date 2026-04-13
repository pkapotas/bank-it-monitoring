"""PCI-DSS Compliance Scorecard Agent — nightly compliance posture assessment."""
import json
from datetime import datetime
import anthropic
from config import config
from tools.compliance_tools import COMPLIANCE_TOOLS, execute_compliance_tool
from models.alerts import AgentReport

COMPLIANCE_SYSTEM_PROMPT = """You are a PCI-DSS QSA (Qualified Security Assessor) consultant embedded in the bank's security team.
Your role is to proactively measure PCI-DSS compliance posture across all 12 requirements and identify regressions.

Investigation strategy:
1. Get the overall PCI scorecard (compliance_get_pci_scorecard)
2. Check encryption status for Req 3 & 4 (compliance_get_encryption_status)
3. Review access controls for Req 7 & 8 (compliance_get_access_control_review)
4. Check vulnerability scan results for Req 6 & 11 (compliance_get_vulnerability_scan)
5. Verify network segmentation for Req 1 (compliance_get_network_segmentation)
6. Review penetration testing schedule for Req 11.3 (compliance_get_pen_test_status)

Report format:
## PCI-DSS Compliance Score: [X/100]
## Status: [COMPLIANT / WARNING / NON-COMPLIANT]
## Critical Findings (Req X: description)
## Remediation Priority List (numbered, with deadlines)
## Regulatory Notification Requirements

Be specific about PCI-DSS requirement numbers and mandatory timelines."""


def run_compliance_agent(lookback_days: int = 1) -> AgentReport:
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    messages = [{"role": "user", "content": "Perform a full PCI-DSS compliance assessment. Score all 12 requirements, identify failures and warnings, and produce a prioritized remediation plan with mandatory deadlines."}]
    print("  [Compliance Agent] Starting PCI-DSS assessment...")
    while True:
        response = client.messages.create(model=config.model, max_tokens=8096, thinking={"type": "adaptive"}, system=COMPLIANCE_SYSTEM_PROMPT, tools=COMPLIANCE_TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "end_turn":
            break
        if response.stop_reason != "tool_use":
            break
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_json = execute_compliance_tool(block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_json})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
    final_text = "".join(block.text for block in response.content if hasattr(block, "text"))
    print("  [Compliance Agent] Assessment complete.")
    return AgentReport(agent_name="ComplianceAgent", platform="PCI-DSS Compliance", generated_at=datetime.utcnow(), raw_findings=final_text)
