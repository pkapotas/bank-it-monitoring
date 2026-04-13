"""
Post-Mortem Generator Agent.
Reads a resolved incident from memory and produces a structured post-mortem document.
"""
import json
from datetime import datetime
import anthropic
from config import config
from models.alerts import AgentReport

POSTMORTEM_SYSTEM_PROMPT = """You are a Site Reliability Engineering lead at a major commercial bank.
Your role is to write thorough, blameless post-mortems for resolved incidents.

Post-mortem format:
## Incident Summary
Title, Severity, Duration, Impact (customers affected, EUR at risk), Escalation required

## Timeline (chronological)
List every key event with timestamp: detection, first response, escalation, diagnosis, fix applied, resolution

## Root Cause Analysis
- Primary root cause (the thing that, if fixed, would have prevented the incident)
- Contributing factors (things that made it worse or harder to detect)
- Detection gap (why wasn't this caught earlier?)

## Impact Assessment
Customer impact, financial impact, SLO impact (error budget consumed), regulatory impact

## What Went Well
Honest assessment of effective response actions

## What Went Wrong
Honest assessment of failures in detection, communication, or resolution

## Action Items (numbered, SMART)
Each action: Owner | Due Date | Priority | Description
Include: monitoring improvements, runbook updates, architectural fixes, process changes

## SLO/SLA Impact
Which SLOs were violated, by how much, error budget remaining

Be blameless, specific, and actionable. Banking post-mortems must be thorough enough to satisfy auditors."""


def run_postmortem_agent(incident: dict) -> AgentReport:
    """
    Generate a post-mortem for a resolved incident.
    incident: dict with keys: id, title, severity, services_affected, summary_text, timeline
    """
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    incident_context = json.dumps(incident, indent=2, default=str)
    messages = [
        {
            "role": "user",
            "content": (
                f"Write a complete post-mortem for the following resolved incident:\n\n"
                f"{incident_context}\n\n"
                "Produce a thorough, blameless post-mortem following the standard format. "
                "Include specific action items with owners and due dates. "
                "Ensure the document is audit-ready for PCI-DSS and SOX review."
            ),
        }
    ]
    print(f"  [PostMortem Agent] Generating post-mortem for {incident.get('id', 'incident')}...")
    response = client.messages.create(
        model=config.model,
        max_tokens=8096,
        thinking={"type": "adaptive"},
        system=POSTMORTEM_SYSTEM_PROMPT,
        messages=messages,
    )
    final_text = "".join(block.text for block in response.content if hasattr(block, "text"))
    print("  [PostMortem Agent] Post-mortem complete.")
    return AgentReport(
        agent_name="PostMortemAgent",
        platform="Incident Management",
        generated_at=datetime.utcnow(),
        raw_findings=final_text,
    )


def get_mock_postmortem() -> dict:
    """Return a pre-written post-mortem for the demo dashboard."""
    return {
        "incident_id":    "INC-00001",
        "generated_at":   "2026-03-22T09:00:00Z",
        "title":          "Payment Gateway Degradation — Clearing-House Certificate Expiry",
        "severity":       "P1 CRITICAL",
        "duration_min":   38,
        "author":         "PostMortem Agent (Claude claude-opus-4-6)",
        "status":         "APPROVED",
        "sections": {
            "summary": "The payment-gateway service experienced a 4.9% error rate for 38 minutes due to an expired TLS certificate on the upstream clearing-house API. 412 customers were unable to complete payments. EUR 18.2M in transactions were delayed (not lost). Escalation to CTO was triggered.",
            "root_cause": "The clearing-house API certificate expired at 23:14 UTC. The automated certificate rotation process had a misconfigured notification channel (Slack webhook URL changed 6 weeks prior but not updated in the rotation script). The payment-gateway CircuitBreaker opened after 10 consecutive 30s timeouts.",
            "action_items": [
                {"id": "AI-001", "owner": "Platform SRE", "priority": "P1", "due": "2026-03-25", "action": "Audit all external API certificate expiry dates; add 30/14/7-day alerts to PagerDuty"},
                {"id": "AI-002", "owner": "Platform SRE", "priority": "P1", "due": "2026-03-23", "action": "Fix notification channel references in all cert-rotation scripts"},
                {"id": "AI-003", "owner": "Payments Eng", "priority": "P2", "due": "2026-04-05", "action": "Implement secondary clearing-house failover; test monthly"},
                {"id": "AI-004", "owner": "Monitoring",  "priority": "P2", "due": "2026-04-01", "action": "Add synthetic monitor for clearing-house API cert validity"},
            ],
        },
    }
