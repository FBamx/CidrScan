from datetime import datetime, timezone

import pytest
from textual.widgets import Button, DataTable, Input, Static

from cidrscan.models import ScanResult
from cidrscan.tui import CidrScanApp, ResultReceived, ScanComplete


def _make_result(ip: str, alive: bool) -> ScanResult:
    return ScanResult(
        ip=ip,
        alive=alive,
        latency_ms=1.5 if alive else None,
        scanned_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


def _fake_scan(*ips_alive: tuple[str, bool]):
    results = [_make_result(ip, alive) for ip, alive in ips_alive]

    async def _gen(*args, **kwargs):
        for r in results:
            yield r

    return _gen


# ── mount / compose ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_app_mounts():
    app = CidrScanApp()
    async with app.run_test() as pilot:
        assert pilot.app.query_one("#result-table", DataTable)
        assert pilot.app.query_one("#btn-scan", Button)
        assert pilot.app.query_one("#input-cidr", Input)


@pytest.mark.asyncio
async def test_table_has_columns():
    app = CidrScanApp()
    async with app.run_test() as pilot:
        table = pilot.app.query_one("#result-table", DataTable)
        col_labels = [str(c.label) for c in table.columns.values()]
        assert "IP Address" in col_labels
        assert "Status" in col_labels
        assert "Latency (ms)" in col_labels


# ── initial CIDR pre-fill ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initial_cidr_prefilled():
    app = CidrScanApp(cidr="10.0.0.1/32")
    async with app.run_test() as pilot:
        value = pilot.app.query_one("#input-cidr", Input).value
        assert value == "10.0.0.1/32"


# ── result rendering ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_result_received_adds_row():
    app = CidrScanApp()
    async with app.run_test() as pilot:
        app.post_message(ResultReceived(_make_result("10.0.0.1", True)))
        await pilot.pause()
        table = pilot.app.query_one("#result-table", DataTable)
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_multiple_results_add_rows():
    app = CidrScanApp()
    async with app.run_test() as pilot:
        for ip in ["10.0.0.1", "10.0.0.2", "10.0.0.3"]:
            app.post_message(ResultReceived(_make_result(ip, True)))
        await pilot.pause()
        table = pilot.app.query_one("#result-table", DataTable)
        assert table.row_count == 3


# ── stats refresh ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stats_update_after_results():
    app = CidrScanApp()
    async with app.run_test() as pilot:
        app.post_message(ResultReceived(_make_result("10.0.0.1", True)))
        app.post_message(ResultReceived(_make_result("10.0.0.2", False)))
        await pilot.pause()
        alive_stat = str(pilot.app.query_one("#stat-alive", Static).render())
        dead_stat = str(pilot.app.query_one("#stat-dead", Static).render())
        assert "1" in alive_stat
        assert "1" in dead_stat


# ── scan complete notification ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scan_complete_does_not_crash():
    app = CidrScanApp()
    async with app.run_test() as pilot:
        app.post_message(ResultReceived(_make_result("10.0.0.1", True)))
        app.post_message(ScanComplete())
        await pilot.pause()  # should not raise


# ── invalid CIDR ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_cidr_shows_notification():
    app = CidrScanApp()
    async with app.run_test() as pilot:
        await pilot.click("#input-cidr")
        await pilot.press("ctrl+a")
        for ch in "not-a-cidr":
            await pilot.press(ch)
        await pilot.click("#btn-scan")
        await pilot.pause()
        # App should still be running (not crashed)
        assert not app._exit


# ── export CSV ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_csv_no_results_no_crash():
    app = CidrScanApp()
    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()  # should not raise


@pytest.mark.asyncio
async def test_export_csv_writes_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = CidrScanApp()
    async with app.run_test() as pilot:
        app.post_message(ResultReceived(_make_result("10.0.0.1", True)))
        await pilot.pause()
        app.action_export_csv()
        await pilot.pause()
        assert (tmp_path / "cidrscan_results.csv").exists()
