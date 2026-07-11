"""
CLI interface for Hermes Terminal using Typer and Rich
"""

import sys
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from .app import HermesTerminal
from .config import load_settings, create_default_config
from .models import CommandRisk

# Initialize CLI
app = typer.Typer(
    help="Hermes Terminal - Remote system control with AI assistance",
    no_args_is_help=True,
)
console = Console()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Global app instance
_app_instance: Optional[HermesTerminal] = None


def get_app() -> HermesTerminal:
    """Get or create app instance"""
    global _app_instance
    if _app_instance is None:
        _app_instance = HermesTerminal()
    return _app_instance


@app.command()
def main():
    """Interactive menu for Hermes Terminal"""
    app_instance = get_app()
    app_instance.start_session()

    console.print(
        Panel(
            "[bold cyan]Hermes Command Center[/bold cyan]",
            expand=False,
            style="cyan",
        )
    )

    while True:
        try:
            console.print()
            console.print(f"[yellow]Current Host:[/yellow] {app_instance.current_host}")
            console.print()

            options = [
                "1. Manual shell",
                "2. AI assistant",
                "3. AI command builder",
                "4. Select target machine",
                "5. Host status",
                "6. Command history",
                "7. Configuration",
                "8. Exit",
            ]

            for opt in options:
                console.print(opt)

            choice = Prompt.ask("[bold]Select option[/bold]", choices=[str(i) for i in range(1, 9)])

            if choice == "1":
                manual_shell(app_instance)
            elif choice == "2":
                ai_assistant(app_instance)
            elif choice == "3":
                ai_command_builder(app_instance)
            elif choice == "4":
                select_host(app_instance)
            elif choice == "5":
                host_status(app_instance)
            elif choice == "6":
                show_history(app_instance)
            elif choice == "7":
                show_config(app_instance)
            elif choice == "8":
                console.print("[yellow]Goodbye![/yellow]")
                app_instance.end_session()
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")
            app_instance.end_session()
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def manual_shell(app_instance: HermesTerminal):
    """Interactive manual shell mode"""
    console.print(f"\n[bold green]Manual Shell - {app_instance.current_host}[/bold green]")
    console.print("[dim]Commands: /host <name>, /ai, /build, /exit[/dim]\n")

    while True:
        try:
            prompt_text = f"[{app_instance.current_host}] $ "
            command = Prompt.ask(prompt_text).strip()

            if not command:
                continue

            if command == "/exit":
                break
            elif command.startswith("/host "):
                host_name = command[6:].strip()
                if app_instance.switch_host(host_name):
                    console.print(f"[green]Switched to {host_name}[/green]")
                else:
                    console.print(f"[red]Failed to switch to {host_name}[/red]")
                continue
            elif command == "/ai":
                console.print("[yellow]Switching to AI Assistant mode[/yellow]")
                break
            elif command == "/build":
                console.print("[yellow]Switching to AI Command Builder mode[/yellow]")
                break

            risk, explanation = app_instance.classify_command(command)
            if risk == CommandRisk.BLOCKED:
                console.print(f"[red]Blocked: {explanation}[/red]")
                continue
            approved = risk == CommandRisk.SAFE
            if risk == CommandRisk.CAUTION:
                approved = Confirm.ask(
                    f"[yellow]CAUTION[/yellow] on {app_instance.current_host}: {command}\nApprove?",
                    default=False,
                )
            elif risk == CommandRisk.DANGER:
                expected = f"CONFIRM {app_instance.current_host} execute"
                entered = Prompt.ask(
                    f"[red]DANGER[/red] Type exactly: [bold]{expected}[/bold]"
                )
                approved = entered == expected
            if not approved:
                console.print("[yellow]Command not executed.[/yellow]")
                continue

            # Execute only after the safety gate above.
            with console.status("[bold green]Executing..."):
                exit_code, stdout, stderr = app_instance.execute_command(
                    command, require_approval=False
                )

            if exit_code == 0:
                console.print(f"[green]✓[/green] {exit_code}")
            else:
                console.print(f"[red]✗[/red] {exit_code}")

            if stdout:
                console.print(stdout)
            if stderr:
                console.print(f"[red]{stderr}[/red]")
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def ai_assistant(app_instance: HermesTerminal):
    """AI assistant mode"""
    console.print(f"\n[bold green]AI Assistant - {app_instance.current_host}[/bold green]")
    console.print("[dim]Describe what you need to do. Type '/exit' to return to menu.[/dim]\n")

    if not app_instance.ai_provider:
        console.print(
            "[red]AI provider not available. Configure Ollama or OpenAI in .env[/red]"
        )
        return

    while True:
        try:
            request = Prompt.ask("[bold]What do you need?[/bold]").strip()

            if request == "/exit":
                break

            if not request:
                continue

            with console.status("[bold cyan]Analyzing..."):
                plan = app_instance.generate_command_plan(request)

            if plan:
                console.print("\n[bold]AI Response:[/bold]")
                console.print(plan["ai_response"])
                console.print("\n[yellow]Note: Review the proposed commands carefully before execution.[/yellow]")
            else:
                console.print("[red]Failed to generate plan[/red]")
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def ai_command_builder(app_instance: HermesTerminal):
    """AI command builder mode"""
    console.print(f"\n[bold green]AI Command Builder - {app_instance.current_host}[/bold green]")
    console.print("[dim]Describe the outcome you want. Type '/exit' to return to menu.[/dim]\n")

    if not app_instance.ai_provider:
        console.print(
            "[red]AI provider not available. Configure Ollama or OpenAI in .env[/red]"
        )
        return

    while True:
        try:
            request = Prompt.ask("[bold]What do you want to achieve?[/bold]").strip()

            if request == "/exit":
                break

            if not request:
                continue

            with console.status("[bold cyan]Generating commands..."):
                plan = app_instance.generate_command_plan(request)

            if plan:
                console.print("\n[bold]Proposed Commands:[/bold]")
                console.print(plan["ai_response"])
                console.print(
                    "\n[yellow][r] Run  [e] Edit  [c] Copy  [s] Save  [x] Cancel[/yellow]"
                )
            else:
                console.print("[red]Failed to generate commands[/red]")
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def select_host(app_instance: HermesTerminal):
    """Select target machine"""
    hosts = app_instance.host_registry.list_hosts()
    console.print("\n[bold]Available Hosts:[/bold]")

    for i, host in enumerate(hosts, 1):
        host_config = app_instance.host_registry.get_host(host)
        description = host_config.description if host_config else "Unknown"
        console.print(f"{i}. {host:15} - {description}")

    try:
        choice = int(
            Prompt.ask(
                "[bold]Select host[/bold]", choices=[str(i) for i in range(1, len(hosts) + 1)]
            )
        )
        selected = hosts[choice - 1]
        if app_instance.switch_host(selected):
            console.print(f"[green]Switched to {selected}[/green]")
    except (ValueError, IndexError):
        console.print("[red]Invalid selection[/red]")


def host_status(app_instance: HermesTerminal):
    """Show host status"""
    console.print(f"\n[bold]Host Status: {app_instance.current_host}[/bold]")

    host_config = app_instance.host_registry.get_host(app_instance.current_host)
    if host_config:
        table = Table(show_header=False)
        table.add_row("Name", app_instance.current_host)
        table.add_row("Description", host_config.description)
        table.add_row("Connection", host_config.connection.value)
        if host_config.hostname:
            table.add_row("Hostname", host_config.hostname)
        table.add_row("OS", host_config.operating_system.value)
        console.print(table)


def show_history(app_instance: HermesTerminal):
    """Show command history"""
    history = app_instance.get_command_history(limit=10)
    console.print(f"\n[bold]Recent Commands on {app_instance.current_host}:[/bold]")

    if history:
        table = Table()
        table.add_column("Command")
        table.add_column("Exit Code")
        table.add_column("Time")

        for cmd in history:
            exit_code = cmd.get("exit_code", "?")
            exit_color = "green" if exit_code == 0 else "red"
            table.add_row(
                cmd.get("command", "")[:50],
                f"[{exit_color}]{exit_code}[/{exit_color}]",
                cmd.get("start_time", "?"),
            )

        console.print(table)
    else:
        console.print("[dim]No command history[/dim]")


def show_config(app_instance: HermesTerminal):
    """Show configuration"""
    console.print("\n[bold]Configuration:[/bold]")
    settings = app_instance.settings

    table = Table()
    table.add_column("Setting")
    table.add_column("Value")

    table.add_row("AI Provider", settings.ai_provider)
    table.add_row("Ollama URL", settings.ollama_base_url)
    table.add_row("Ollama Model", settings.ollama_model)
    table.add_row("Config Dir", str(settings.config_dir))
    table.add_row("Database", str(settings.database_path))
    table.add_row("SSH Timeout", str(settings.ssh_timeout))

    console.print(table)


# Subcommands
@app.command()
def manual():
    """Start in manual shell mode"""
    app_instance = get_app()
    app_instance.start_session("manual")
    try:
        manual_shell(app_instance)
    finally:
        app_instance.end_session()


@app.command()
def ai_mode():
    """Start in AI assistant mode"""
    app_instance = get_app()
    app_instance.start_session("ai_assistant")
    try:
        ai_assistant(app_instance)
    finally:
        app_instance.end_session()


@app.command("ai")
def ai():
    """Start in AI assistant mode."""
    ai_mode()


@app.command()
def build():
    """Start in AI command builder mode"""
    app_instance = get_app()
    app_instance.start_session("command_builder")
    try:
        ai_command_builder(app_instance)
    finally:
        app_instance.end_session()


@app.command()
def hosts_list():
    """List available hosts"""
    app_instance = get_app()
    host_list = app_instance.host_registry.list_hosts()
    console.print("[bold]Available Hosts:[/bold]")

    table = Table()
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("OS")

    for host_name in host_list:
        host_config = app_instance.host_registry.get_host(host_name)
        if host_config:
            table.add_row(
                host_name,
                host_config.description,
                host_config.operating_system.value,
            )

    console.print(table)


@app.command("hosts")
def hosts():
    """List configured hosts without connecting to them."""
    hosts_list()


@app.command("setup")
def setup():
    """Create local configuration using safe example defaults."""
    settings = load_settings()
    create_default_config()
    hosts_path = settings.config_dir / "hosts.yaml"
    policy_path = settings.config_dir / "policy.yaml"
    project_root = Path(__file__).resolve().parents[2]
    defaults = {
        hosts_path: """hosts:
  gateway:
    connection: local
    description: Gateway WSL control node
  core:
    connection: ssh
    hostname: 192.168.1.84
    user: root
    operating_system: proxmox
    ssh_key: ~/.ssh/hermes_key
  kali:
    connection: ssh
    hostname: hermes-kali
    user: roy
    operating_system: kali
    ssh_key: ~/.ssh/hermes_key
""",
        policy_path: """safety_policy:
  enable_dangerous_confirmation: true
  dangerous_confirmation_prefix: CONFIRM
  require_approval_for: [caution, danger]
  blocked_patterns: [eval, exec, base64 -d, '| sh', '| bash']
  log_all_commands: true
""",
    }
    for destination, example in (
        (hosts_path, project_root / "config" / "hosts.example.yaml"),
        (policy_path, project_root / "config" / "policy.example.yaml"),
    ):
        if destination.exists():
            console.print(f"[dim]Kept existing {destination}[/dim]")
        else:
            content = example.read_text(encoding="utf-8") if example.exists() else defaults[destination]
            destination.write_text(content, encoding="utf-8")
            console.print(f"[green]Created {destination}[/green]")
    console.print("Setup complete. Remote connections occur only when you explicitly select a remote host.")


@app.command()
def status():
    """Show host status"""
    app_instance = get_app()
    host_status(app_instance)


@app.command()
def history(host: Optional[str] = None, limit: int = 50):
    """Show command history"""
    app_instance = get_app()
    cmd_history = app_instance.get_command_history(host, limit)
    console.print("[bold]Command History[/bold]")

    if cmd_history:
        table = Table()
        table.add_column("Time")
        table.add_column("Host")
        table.add_column("Command")
        table.add_column("Exit")

        for cmd in cmd_history:
            exit_code = cmd.get("exit_code", "?")
            exit_color = "green" if exit_code == 0 else "red"
            table.add_row(
                cmd.get("start_time", "")[:19],
                cmd.get("host", ""),
                cmd.get("command", "")[:40],
                f"[{exit_color}]{exit_code}[/{exit_color}]",
            )

        console.print(table)
    else:
        console.print("[dim]No history found[/dim]")


@app.command()
def doctor():
    """Diagnostic check"""
    app_instance = get_app()
    console.print("[bold]Hermes Terminal Diagnostic[/bold]\n")

    checks = [
        ("Python Version", f"{sys.version.split()[0]}", True),
        ("Config Directory", str(app_instance.settings.config_dir), True),
        ("Database", str(app_instance.settings.database_path), True),
        ("AI Provider", app_instance.settings.ai_provider, True),
        ("AI Available", "Yes" if app_instance.ai_provider else "No", True),
    ]

    table = Table()
    table.add_column("Check")
    table.add_column("Status")

    for check_name, status, _ in checks:
        table.add_row(check_name, status)

    console.print(table)


def cli_main():
    """Main entry point for CLI"""
    app()
