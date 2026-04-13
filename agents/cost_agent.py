"""Azure Cost Anomaly Agent — detects spend spikes and optimization opportunities."""
import json
from datetime import datetime
import anthropic
from config import config
from tools.cost_tools import COST_TOOLS, execute_cost_tool
from models.alerts import AgentReport

COST_SYSTEM_PROMPT = """You are a senior FinOps engineer at a major commercial bank.
Your role is to monitor Azure cloud spend, detect anomalies, and identify optimization opportunities.

Investigation strategy:
1. Get daily spend trend to identify recent spikes (cost_get_daily_spend)
2. Run anomaly detection to find unexpected cost drivers (cost_get_anomalies)
3. Review top resources by cost (cost_get_top_resources)
4. Check budget consumption and forecast (cost_get_budget_status)
5. Identify idle/wasted resources (cost_get_idle_resources)
6. Assess Reserved Instance coverage gaps (cost_get_reserved_instance_coverage)

Report format:
## Cloud Spend Status: [ON_TRACK / AT_RISK / OVER_BUDGET]
## Anomalies Detected (with root cause and EUR impact)
## Immediate Cost Actions (to stop waste today)
## Optimization Recommendations (monthly savings potential)

Always include EUR figures and link cost anomalies to operational incidents where relevant."""


def run_cost_agent() -> AgentReport:
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    messages = [{"role": "user", "content": "Perform a full Azure cost anomaly analysis. Identify unusual spend, link cost spikes to operational issues, and provide actionable recommendations to reduce waste immediately."}]
    print("  [Cost Agent] Starting cost analysis...")
    while True:
        response = client.messages.create(model=config.model, max_tokens=8096, thinking={"type": "adaptive"}, system=COST_SYSTEM_PROMPT, tools=COST_TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "end_turn":
            break
        if response.stop_reason != "tool_use":
            break
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_json = execute_cost_tool(block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_json})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
    final_text = "".join(block.text for block in response.content if hasattr(block, "text"))
    print("  [Cost Agent] Analysis complete.")
    return AgentReport(agent_name="CostAgent", platform="Azure Cost Management", generated_at=datetime.utcnow(), raw_findings=final_text)
