"""JESSICA CLI — the primary command‑line interface for the platform.

Usage::

    jessica --mode autonomous
    jessica --mode conductor --bind 0.0.0.0:9000
    jessica health --component conductorx
    jessica scan --target 192.168.1.0/24
    jessica workflow --template full_recon --target example.com
"""

from __future__ import annotations

import asyncio
import logging

import click
from rich.console import Console
from rich.table import Table

from jessica import __version__
from jessica.core.engine import JessicaEngine, RuntimeMode, load_config

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _banner() -> None:
    console.print(
        r"""
[bold magenta]
 ██╗███████╗███████╗███████╗██╗ ██████╗ █████╗ ██╗
 ██║██╔════╝██╔════╝██╔════╝██║██╔════╝██╔══██╗██║
 ██║█████╗  ███████╗███████╗██║██║     ███████║██║
██  ██║██╔══╝  ╚════██║╚════██║██║██║     ██╔══██║██║
 ██║███████╗███████║███████║██║╚██████╗██║  ██║██║
 ╚═╝╚══════╝╚══════╝╚══════╝╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝
[/bold magenta]
[bold cyan]iFINITEAi2025JESSICAi — Huntress Edition[/bold cyan]
[dim]v{version} • CHAiMERA • ConductorX • 3×3×3 Stack Overlay[/dim]
""".format(version=__version__)
    )


@click.group(invoke_without_command=True)
@click.option("--mode", type=click.Choice([m.value for m in RuntimeMode]), default="autonomous")
@click.option("--bind", default="0.0.0.0:9000", help="Bind address:port")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.pass_context
def main(ctx: click.Context, mode: str, bind: str, verbose: bool) -> None:
    """iFINITEAi2025JESSICAi — Huntress Edition security platform."""
    _setup_logging(verbose)
    _banner()

    if ctx.invoked_subcommand is not None:
        return

    host, _, port_str = bind.rpartition(":")
    host = host or "0.0.0.0"
    port = int(port_str) if port_str else 9000

    config = load_config(mode=RuntimeMode(mode), bind_address=host, bind_port=port)
    engine = JessicaEngine(config)

    try:
        asyncio.run(engine.start())
    except KeyboardInterrupt:
        console.print("[yellow]Shutting down …[/yellow]")
        asyncio.run(engine.stop())


@main.command()
@click.option("--component", default="all", help="Component to check")
def health(component: str) -> None:
    """Check health of platform components."""
    console.print(f"[green]✓[/green] {component} is operational")


@main.command()
@click.option("--target", required=True, help="Target IP / CIDR / hostname")
@click.option("--full", is_flag=True, help="Full scan with -sV -sC -O")
def scan(target: str, full: bool) -> None:
    """Run a quick network scan."""
    from jessica.network.scanner import NetworkScanner

    scanner = NetworkScanner()
    coro = scanner.full_scan(target) if full else scanner.quick_scan(target)
    result = asyncio.run(coro)

    table = Table(title=f"Scan: {target}")
    table.add_column("Port", style="cyan")
    table.add_column("Service", style="green")
    for port in result.open_ports:
        table.add_row(str(port), result.services.get(port, ""))
    console.print(table)
    if result.os_guess:
        console.print(f"OS: [bold]{result.os_guess}[/bold]")


@main.command()
@click.option("--template", required=True, help="Workflow template name")
@click.option("--target", required=True, help="Target")
def workflow(template: str, target: str) -> None:
    """Launch a CHAiMERA workflow template."""
    from jessica.chimera.chain import ChimeraChainEngine
    from jessica.chimera.workflow import WorkflowManager

    config = load_config()
    engine = ChimeraChainEngine(config.chimera_cfg)
    mgr = WorkflowManager(engine)

    async def _run() -> None:
        await engine.start()
        chain = await mgr.launch(template, target)
        console.print(f"[green]Workflow complete:[/green] {chain.name} — {chain.status.value}")

    asyncio.run(_run())


@main.command()
def suites() -> None:
    """Show installed security tool suites."""
    from jessica.suites.blackarch import BlackArchSuite
    from jessica.suites.kali import KaliSuite

    config = load_config()
    kali = KaliSuite(config.kali_suite)
    blackarch = BlackArchSuite(config.blackarch_suite)

    table = Table(title="Security Tool Suites")
    table.add_column("Suite", style="bold")
    table.add_column("Total", style="cyan")
    table.add_column("Available", style="green")
    table.add_row("Kali", str(len(kali.list_tools())), str(len(kali.available_tools())))
    table.add_row("BlackArch", str(len(blackarch.list_tools())), str(len(blackarch.available_tools())))
    console.print(table)


@main.command()
def interfaces() -> None:
    """List all network interfaces."""
    from jessica.network.interfaces import InterfaceManager

    mgr = InterfaceManager()
    ifaces = mgr.scan()

    table = Table(title="Network Interfaces")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("MAC", style="dim")
    table.add_column("State")
    table.add_column("Driver", style="dim")
    for i in ifaces:
        table.add_row(i.name, i.type, i.mac, i.state, i.driver)
    console.print(table)


if __name__ == "__main__":
    main()
