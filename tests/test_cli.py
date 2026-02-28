from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from cidrscan.cli import app
from cidrscan.models import ScanResult

runner = CliRunner()


def _make_result(ip: str, alive: bool) -> ScanResult:
    return ScanResult(
        ip=ip,
        alive=alive,
        latency_ms=1.5 if alive else None,
        scanned_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


def _fake_scan(*ips_alive: tuple[str, bool]):
    """Return an async generator that yields the given (ip, alive) pairs."""
    results = [_make_result(ip, alive) for ip, alive in ips_alive]

    async def _gen(*args, **kwargs):
        for r in results:
            yield r

    return _gen


# ── argument validation ────────────────────────────────────────────────────────

def test_invalid_cidr_rejected():
    result = runner.invoke(app, ["not-a-cidr"])
    assert result.exit_code != 0
    assert "Invalid value" in result.output or result.exit_code == 2


def test_valid_cidr_accepted():
    fake = _fake_scan(("10.0.0.1", True), ("10.0.0.2", False))
    with patch("cidrscan.cli.scan_cidr", new=fake):
        result = runner.invoke(app, ["10.0.0.0/30"])
    assert result.exit_code == 0  # at least one alive → exit 0


# ── exit codes ────────────────────────────────────────────────────────────────

def test_exit_0_when_any_alive():
    fake = _fake_scan(("192.168.0.1", True))
    with patch("cidrscan.cli.scan_cidr", new=fake):
        result = runner.invoke(app, ["192.168.0.1/32"])
    assert result.exit_code == 0


def test_exit_1_when_all_dead():
    fake = _fake_scan(("192.168.0.1", False))
    with patch("cidrscan.cli.scan_cidr", new=fake):
        result = runner.invoke(app, ["192.168.0.1/32"])
    assert result.exit_code == 1


# ── output formats ────────────────────────────────────────────────────────────
# Format correctness is covered by test_output.py; here we verify that the CLI
# passes the right arguments to output_results.

def test_json_output_format():
    fake = _fake_scan(("10.0.0.1", True), ("10.0.0.2", False))
    with patch("cidrscan.cli.scan_cidr", new=fake), \
         patch("cidrscan.cli.output_results") as mock_out, \
         patch("cidrscan.cli.print_summary"):
        result = runner.invoke(app, ["10.0.0.0/30", "--output", "json"])
    assert result.exit_code == 0
    mock_out.assert_called_once()
    _, kwargs = mock_out.call_args
    assert kwargs["fmt"] == "json"


def test_csv_output_format():
    fake = _fake_scan(("10.0.0.1", True), ("10.0.0.2", False))
    with patch("cidrscan.cli.scan_cidr", new=fake), \
         patch("cidrscan.cli.output_results") as mock_out, \
         patch("cidrscan.cli.print_summary"):
        result = runner.invoke(app, ["10.0.0.0/30", "--output", "csv"])
    assert result.exit_code == 0
    _, kwargs = mock_out.call_args
    assert kwargs["fmt"] == "csv"


def test_alive_only_flag():
    fake = _fake_scan(("10.0.0.1", True), ("10.0.0.2", False))
    with patch("cidrscan.cli.scan_cidr", new=fake), \
         patch("cidrscan.cli.output_results") as mock_out, \
         patch("cidrscan.cli.print_summary"):
        result = runner.invoke(app, ["10.0.0.0/30", "--alive-only"])
    assert result.exit_code == 0
    _, kwargs = mock_out.call_args
    assert kwargs["alive_only"] is True


# ── options passthrough ────────────────────────────────────────────────────────

def test_concurrency_and_timeout_passed_to_scanner():
    captured: dict = {}

    async def capturing_scan(cidr, *, concurrency, timeout):
        captured["concurrency"] = concurrency
        captured["timeout"] = timeout
        yield _make_result("10.0.0.1", True)

    with patch("cidrscan.cli.scan_cidr", new=capturing_scan):
        runner.invoke(app, ["10.0.0.0/30", "-c", "50", "-t", "2.5"])

    assert captured["concurrency"] == 50
    assert captured["timeout"] == 2.5
