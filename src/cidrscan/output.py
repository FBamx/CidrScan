import csv
import io
import json
import sys
from typing import Literal

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from cidrscan.models import ScanResult

OutputFormat = Literal["table", "json", "csv"]

_ALIVE_STYLE = "bold green"
_DEAD_STYLE = "dim"


def _make_progress(total: int) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=Console(stderr=True),
        transient=True,
    )


# ── table ─────────────────────────────────────────────────────────────────────

def render_table(results: list[ScanResult], *, alive_only: bool = False) -> None:
    console = Console()
    table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=False)
    table.add_column("IP Address", style="", min_width=16)
    table.add_column("Status", min_width=8)
    table.add_column("Latency (ms)", justify="right", min_width=12)
    table.add_column("Scanned At", min_width=24)

    for r in results:
        if alive_only and not r.alive:
            continue
        style = _ALIVE_STYLE if r.alive else _DEAD_STYLE
        table.add_row(
            r.ip,
            "alive" if r.alive else "dead",
            f"{r.latency_ms:.2f}" if r.latency_ms is not None else "-",
            r.scanned_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            style=style,
        )

    console.print(table)


# ── json ──────────────────────────────────────────────────────────────────────

def render_json(results: list[ScanResult], *, alive_only: bool = False) -> str:
    rows = [
        {
            "ip": r.ip,
            "alive": r.alive,
            "latency_ms": r.latency_ms,
            "scanned_at": r.scanned_at.isoformat(),
        }
        for r in results
        if not (alive_only and not r.alive)
    ]
    return json.dumps(rows, indent=2)


# ── csv ───────────────────────────────────────────────────────────────────────

def render_csv(results: list[ScanResult], *, alive_only: bool = False) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["ip", "alive", "latency_ms", "scanned_at"])
    writer.writeheader()
    for r in results:
        if alive_only and not r.alive:
            continue
        writer.writerow(
            {
                "ip": r.ip,
                "alive": r.alive,
                "latency_ms": r.latency_ms if r.latency_ms is not None else "",
                "scanned_at": r.scanned_at.isoformat(),
            }
        )
    return buf.getvalue()


# ── summary ───────────────────────────────────────────────────────────────────

def print_summary(results: list[ScanResult]) -> None:
    console = Console(stderr=True)
    total = len(results)
    alive = sum(1 for r in results if r.alive)
    latencies = [r.latency_ms for r in results if r.latency_ms is not None]
    avg = sum(latencies) / len(latencies) if latencies else None

    console.print(
        f"\n[bold]Summary:[/bold] {alive}/{total} alive"
        + (f", avg latency [green]{avg:.1f} ms[/green]" if avg is not None else ""),
        highlight=False,
    )


# ── public API ────────────────────────────────────────────────────────────────

def output_results(
    results: list[ScanResult],
    fmt: OutputFormat,
    *,
    alive_only: bool = False,
    out_file: str | None = None,
) -> None:
    """Render results in the requested format, writing to stdout or a file."""
    if fmt == "table":
        if out_file:
            # Redirect rich output to file (plain text, no colour codes)
            file_console = Console(
                file=open(out_file, "w"), highlight=False, markup=False
            )
            table = Table(show_header=True, box=None, pad_edge=False)
            table.add_column("IP Address")
            table.add_column("Status")
            table.add_column("Latency (ms)")
            table.add_column("Scanned At")
            for r in results:
                if alive_only and not r.alive:
                    continue
                table.add_row(
                    r.ip,
                    "alive" if r.alive else "dead",
                    f"{r.latency_ms:.2f}" if r.latency_ms is not None else "-",
                    r.scanned_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                )
            file_console.print(table)
        else:
            render_table(results, alive_only=alive_only)

    elif fmt == "json":
        text = render_json(results, alive_only=alive_only)
        _write(text, out_file)

    elif fmt == "csv":
        text = render_csv(results, alive_only=alive_only)
        _write(text, out_file)


def _write(text: str, out_file: str | None) -> None:
    if out_file:
        with open(out_file, "w") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
