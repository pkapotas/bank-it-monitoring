"""
Bank IT Operations Multi-Agent Monitoring System
================================================
Entry point for the multi-agent monitoring system that integrates:
  - Dynatrace  (APM, infrastructure health, SLOs, synthetics)
  - Azure Monitor (cloud platform, AKS, Defender for Cloud)
  - Kibana/ELK (log analytics, SIEM, APM traces)

Usage:
  python main.py                       # Run a full monitoring cycle (last 60 minutes)
  python main.py --lookback 30         # Analyse the last 30 minutes
  python main.py --agent dynatrace     # Run only the Dynatrace agent
  python main.py --agent azure         # Run only the Azure agent
  python main.py --agent kibana        # Run only the Kibana agent
  python main.py --output report.txt   # Save report to file
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich import print as rprint

from config import config
from agents.orchestrator import run_orchestrator
from agents.dynatrace_agent import run_dynatrace_agent
from agents.azure_agent import run_azure_agent
from agents.kibana_agent import run_kibana_agent
from models.alerts import MonitoringReport


console = Console()


def print_banner():
    console.print()
    console.print(Panel.fit(
        "[bold blue]Bank IT Operations — Multi-Agent Monitoring System[/bold blue]\n"
        "[dim]Powered by Claude claude-opus-4-6 + Dynatrace + Azure Monitor + Kibana[/dim]",
        border_style="blue"
    ))
    console.print()


def print_report(report: MonitoringReport):
    """Render the monitoring report to the console with Rich formatting."""
    status_colors = {
        "healthy": "green",
        "degraded": "yellow",
        "critical": "red",
        "unknown": "dim",
    }
    status_color = status_colors.get(report.overall_status, "dim")

    console.print(Rule(f"[{status_color}]MONITORING REPORT — {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}[/{status_color}]"))
    console.print()

    # Overall status badge
    console.print(
        Panel(
            f"[bold {status_color}]OVERALL STATUS: {report.overall_status.upper()}[/bold {status_color}]"
            + ("\n[bold red]⚠ ESCALATION REQUIRED[/bold red]" if report.escalation_required else ""),
            border_style=status_color,
            expand=False,
        )
    )
    console.print()

    # Sub-agent reports
    if report.dynatrace_report:
        console.print(Panel(
            report.dynatrace_report.raw_findings or "[dim]No findings[/dim]",
            title="[cyan]Dynatrace Report[/cyan]",
            border_style="cyan",
        ))
        console.print()

    if report.azure_report:
        console.print(Panel(
            report.azure_report.raw_findings or "[dim]No findings[/dim]",
            title="[blue]Azure Monitor Report[/blue]",
            border_style="blue",
        ))
        console.print()

    if report.kibana_report:
        console.print(Panel(
            report.kibana_report.raw_findings or "[dim]No findings[/dim]",
            title="[magenta]Kibana / ELK Report[/magenta]",
            border_style="magenta",
        ))
        console.print()

    # Orchestrator synthesis
    if report.incident_summary:
        console.print(Panel(
            report.incident_summary,
            title="[bold yellow]Orchestrator Synthesis — Unified Incident Report[/bold yellow]",
            border_style="yellow",
        ))
    console.print()


def save_report(report: MonitoringReport, output_path: str):
    """Save the report as plain text to a file."""
    path = Path(output_path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"BANK IT OPERATIONS MONITORING REPORT\n")
        f.write(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}\n")
        f.write(f"Overall Status: {report.overall_status.upper()}\n")
        f.write(f"Escalation Required: {'YES' if report.escalation_required else 'NO'}\n")
        f.write("=" * 80 + "\n\n")

        if report.dynatrace_report:
            f.write("=== DYNATRACE REPORT ===\n")
            f.write(report.dynatrace_report.raw_findings or "No findings\n")
            f.write("\n\n")

        if report.azure_report:
            f.write("=== AZURE MONITOR REPORT ===\n")
            f.write(report.azure_report.raw_findings or "No findings\n")
            f.write("\n\n")

        if report.kibana_report:
            f.write("=== KIBANA/ELK REPORT ===\n")
            f.write(report.kibana_report.raw_findings or "No findings\n")
            f.write("\n\n")

        if report.incident_summary:
            f.write("=== ORCHESTRATOR SYNTHESIS ===\n")
            f.write(report.incident_summary)
            f.write("\n")

    console.print(f"[green]Report saved to:[/green] {path.resolve()}")


def validate_config():
    """Check that required environment variables are present."""
    missing = []
    if not config.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        console.print(f"[red]ERROR: Missing required environment variables: {', '.join(missing)}[/red]")
        console.print("[dim]Create a .env file or set environment variables before running.[/dim]")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Bank IT Operations Multi-Agent Monitoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--lookback", type=int, default=60,
        help="Minutes of history to analyse (default: 60)"
    )
    parser.add_argument(
        "--agent", choices=["dynatrace", "azure", "kibana", "all"], default="all",
        help="Which agent to run (default: all)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Save report to this file path"
    )
    args = parser.parse_args()

    print_banner()
    validate_config()

    console.print(f"[dim]Analysis window: last {args.lookback} minutes[/dim]")
    console.print(f"[dim]Model: {config.model}[/dim]")
    console.print()

    try:
        if args.agent == "all":
            report = run_orchestrator(lookback_minutes=args.lookback)
            print_report(report)
            if args.output:
                save_report(report, args.output)

        elif args.agent == "dynatrace":
            agent_report = run_dynatrace_agent(lookback_minutes=args.lookback)
            console.print(Panel(
                agent_report.raw_findings or "[dim]No findings[/dim]",
                title="[cyan]Dynatrace Report[/cyan]",
                border_style="cyan",
            ))

        elif args.agent == "azure":
            agent_report = run_azure_agent(lookback_minutes=args.lookback)
            console.print(Panel(
                agent_report.raw_findings or "[dim]No findings[/dim]",
                title="[blue]Azure Monitor Report[/blue]",
                border_style="blue",
            ))

        elif args.agent == "kibana":
            agent_report = run_kibana_agent(lookback_minutes=args.lookback)
            console.print(Panel(
                agent_report.raw_findings or "[dim]No findings[/dim]",
                title="[magenta]Kibana/ELK Report[/magenta]",
                border_style="magenta",
            ))

    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring run interrupted by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]ERROR: {e}[/red]")
        raise


if __name__ == "__main__":
    main()
