import asyncio
import ipaddress
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from cidrscan.models import ScanResult
from cidrscan.output import OutputFormat, output_results, print_summary
from cidrscan.scanner import scan_cidr

__version__ = "0.1.0"

app = typer.Typer(
    name="cidrscan",
    help="Ping-scan all IPs in a CIDR block and report which ones are alive.",
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"cidrscan version {__version__}")
        raise typer.Exit()


def _err_console() -> Console:
    """Create a stderr Console bound to the *current* sys.stderr.

    Creating it lazily (inside the command) ensures the test runner's
    stream substitution is already in place, so stderr/stdout stay separate.
    """
    return Console(stderr=True)


def _validate_cidr(value: str) -> str:
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise typer.BadParameter(f"{value!r} is not a valid CIDR notation")
    return value


@app.command()
def main(
    cidr: Annotated[
        str,
        typer.Argument(
            help="CIDR block to scan, e.g. 192.168.1.0/24",
            callback=_validate_cidr,
        ),
    ],
    concurrency: Annotated[
        int,
        typer.Option(
            "--concurrency", "-c", help="Max simultaneous pings", min=1, max=65535
        ),
    ] = 100,
    timeout: Annotated[
        float,
        typer.Option("--timeout", "-t", help="Per-ping timeout in seconds", min=0.1),
    ] = 1.0,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
    alive_only: Annotated[
        bool,
        typer.Option("--alive-only", "-a", help="Only show alive hosts"),
    ] = False,
    out_file: Annotated[
        Optional[str],
        typer.Option(
            "--out", "-f", help="Write results to this file instead of stdout"
        ),
    ] = None,
    no_summary: Annotated[
        bool,
        typer.Option("--no-summary", help="Suppress the summary line"),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option("--tui", "-u", help="Launch interactive TUI"),
    ] = False,
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    if tui:
        from cidrscan.tui import run_tui

        run_tui(cidr=cidr, concurrency=concurrency, timeout=timeout)
        return

    err = _err_console()

    network = ipaddress.ip_network(cidr, strict=False)
    hosts = list(network.hosts()) or [network.network_address]
    total = len(hosts)

    err.print(
        f"[bold cyan]CidrScan[/bold cyan] scanning [yellow]{cidr}[/yellow] "
        f"([cyan]{total}[/cyan] host{'s' if total != 1 else ''}, "
        f"concurrency=[cyan]{concurrency}[/cyan], timeout=[cyan]{timeout}s[/cyan])\n"
    )

    results: list[ScanResult] = []

    async def _run() -> None:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=err,
            transient=True,
        )
        with progress:
            task = progress.add_task("Scanning…", total=total)
            async for result in scan_cidr(
                cidr, concurrency=concurrency, timeout=timeout
            ):
                results.append(result)
                progress.advance(task)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        err.print("\n[yellow]Interrupted — showing partial results.[/yellow]")

    if not results:
        err.print("[red]No results collected.[/red]")
        raise typer.Exit(1)

    output_results(results, fmt=output, alive_only=alive_only, out_file=out_file)

    if not no_summary:
        print_summary(results)

    # Exit 0 if at least one host is alive, 1 if all dead (useful for scripting)
    raise typer.Exit(0 if any(r.alive for r in results) else 1)
