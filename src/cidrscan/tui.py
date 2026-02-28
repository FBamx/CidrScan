from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    Static,
)

from cidrscan.models import ScanResult
from cidrscan.output import render_csv
from cidrscan.scanner import scan_cidr

CSS = """
Screen { background: $surface; }

#toolbar {
    height: 3;
    padding: 0 1;
    background: $panel;
    align: left middle;
}
#toolbar Input { width: 24; margin-right: 1; }
#toolbar #input-concurrency, #toolbar #input-timeout { width: 10; }
#toolbar Button { margin-left: 1; }

#body { height: 1fr; }

#table-pane {
    width: 3fr;
    border-right: solid $primary-darken-2;
}

#stats-pane {
    width: 1fr;
    padding: 1 2;
    background: $panel;
}
#stats-pane Label { margin-bottom: 1; }

#progress-bar { height: 1; margin: 0 1; }
"""


@dataclass
class ResultReceived(Message):
    result: ScanResult


@dataclass
class ScanComplete(Message):
    pass


class CidrScanApp(App[None]):
    TITLE = "CidrScan"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "start_scan", "Scan"),
        Binding("e", "export_csv", "Export CSV"),
    ]
    CSS = CSS

    def __init__(
        self,
        cidr: str = "",
        concurrency: int = 100,
        timeout: float = 1.0,
    ) -> None:
        super().__init__()
        self._initial_cidr = cidr
        self._initial_concurrency = concurrency
        self._initial_timeout = timeout
        self._results: list[ScanResult] = []
        self._total = 0
        self._scanned = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="toolbar"):
            yield Input(
                placeholder="CIDR  e.g. 192.168.1.0/24",
                value=self._initial_cidr,
                id="input-cidr",
            )
            yield Input(
                placeholder="Concurrency",
                value=str(self._initial_concurrency),
                id="input-concurrency",
            )
            yield Input(
                placeholder="Timeout (s)",
                value=str(self._initial_timeout),
                id="input-timeout",
            )
            yield Button("Scan", id="btn-scan", variant="primary")
        with Horizontal(id="body"):
            with Vertical(id="table-pane"):
                yield DataTable(id="result-table", zebra_stripes=True)
            with Vertical(id="stats-pane"):
                yield Label("Stats")
                yield Static("Scanned:  -", id="stat-scanned")
                yield Static("Alive:    -", id="stat-alive")
                yield Static("Dead:     -", id="stat-dead")
                yield Static("Avg ms:   -", id="stat-avg")
        yield ProgressBar(id="progress-bar", show_eta=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#result-table", DataTable)
        table.add_columns("IP Address", "Status", "Latency (ms)")
        if self._initial_cidr:
            self.action_start_scan()

    @work(exclusive=True)
    async def _do_scan(
        self, cidr: str, concurrency: int, timeout: float
    ) -> None:
        async for result in scan_cidr(
            cidr, concurrency=concurrency, timeout=timeout
        ):
            self.post_message(ResultReceived(result))
        self.post_message(ScanComplete())

    def on_result_received(self, message: ResultReceived) -> None:
        r = message.result
        self._results.append(r)
        self._scanned += 1

        table = self.query_one("#result-table", DataTable)
        status = "● alive" if r.alive else "○ dead"
        latency = f"{r.latency_ms:.2f}" if r.latency_ms is not None else "-"
        style = "bold green" if r.alive else "dim"
        table.add_row(r.ip, f"[{style}]{status}[/]", latency)

        self._refresh_stats()
        self.query_one("#progress-bar", ProgressBar).advance(1)

    def on_scan_complete(self, _: ScanComplete) -> None:
        self._refresh_stats()
        self.notify("Scan complete.")

    def action_start_scan(self) -> None:
        cidr = self.query_one("#input-cidr", Input).value.strip()
        if not cidr:
            return
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            self.notify(f"Invalid CIDR: {cidr}", severity="error")
            return
        try:
            concurrency = int(
                self.query_one("#input-concurrency", Input).value
            )
            timeout = float(
                self.query_one("#input-timeout", Input).value
            )
        except ValueError:
            self.notify("Invalid concurrency or timeout", severity="error")
            return

        hosts = list(network.hosts()) or [network.network_address]
        self._total = len(hosts)
        self._scanned = 0
        self._results = []

        self.query_one("#result-table", DataTable).clear()
        bar = self.query_one("#progress-bar", ProgressBar)
        bar.update(total=self._total, progress=0)

        self._refresh_stats()
        self._do_scan(cidr, concurrency, timeout)

    def action_export_csv(self) -> None:
        if not self._results:
            self.notify("No results to export.", severity="warning")
            return
        path = "cidrscan_results.csv"
        with open(path, "w") as f:
            f.write(render_csv(self._results))
        self.notify(f"Exported to {path}")

    @on(Button.Pressed, "#btn-scan")
    def on_scan_button(self) -> None:
        self.action_start_scan()

    def _refresh_stats(self) -> None:
        alive = sum(1 for r in self._results if r.alive)
        dead = self._scanned - alive
        latencies = [r.latency_ms for r in self._results if r.latency_ms is not None]
        avg = sum(latencies) / len(latencies) if latencies else None

        self.query_one("#stat-scanned", Static).update(
            f"Scanned:  {self._scanned}/{self._total}"
        )
        self.query_one("#stat-alive", Static).update(f"Alive:    {alive}")
        self.query_one("#stat-dead", Static).update(f"Dead:     {dead}")
        self.query_one("#stat-avg", Static).update(
            f"Avg ms:   {avg:.1f}" if avg is not None else "Avg ms:   -"
        )


def run_tui(cidr: str = "", concurrency: int = 100, timeout: float = 1.0) -> None:
    CidrScanApp(cidr=cidr, concurrency=concurrency, timeout=timeout).run()
