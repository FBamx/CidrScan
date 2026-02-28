import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cidrscan.models import ScanResult
from cidrscan.scanner import _ping_args, _ping_once, scan_cidr

# ── _ping_args ────────────────────────────────────────────────────────────────


def test_ping_args_unix(monkeypatch):
    monkeypatch.setattr("cidrscan.scanner.sys.platform", "linux")
    args = _ping_args("10.0.0.1", timeout=1.0)
    assert args == ["ping", "-c", "1", "-W", "1", "10.0.0.1"]


def test_ping_args_windows(monkeypatch):
    monkeypatch.setattr("cidrscan.scanner.sys.platform", "win32")
    args = _ping_args("10.0.0.1", timeout=2.0)
    assert args == ["ping", "-n", "1", "-w", "2000", "10.0.0.1"]


def test_ping_args_timeout_rounds_up(monkeypatch):
    monkeypatch.setattr("cidrscan.scanner.sys.platform", "linux")
    args = _ping_args("10.0.0.1", timeout=0.3)
    # max(1, int(0.3)) == 1
    assert args[4] == "1"


# ── _ping_once ────────────────────────────────────────────────────────────────


def _make_proc(returncode: int) -> MagicMock:
    proc = MagicMock()
    proc.wait = AsyncMock(return_value=returncode)
    proc.kill = MagicMock()
    return proc


@pytest.mark.asyncio
async def test_ping_once_alive():
    proc = _make_proc(returncode=0)
    with patch(
        "cidrscan.scanner.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        result = await _ping_once("192.168.1.1", timeout=1.0)

    assert result.alive is True
    assert result.latency_ms is not None
    assert result.latency_ms >= 0
    assert result.ip == "192.168.1.1"


@pytest.mark.asyncio
async def test_ping_once_dead():
    proc = _make_proc(returncode=1)
    with patch(
        "cidrscan.scanner.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        result = await _ping_once("192.168.1.2", timeout=1.0)

    assert result.alive is False
    assert result.latency_ms is None


@pytest.mark.asyncio
async def test_ping_once_timeout():
    proc = MagicMock()
    proc.wait = AsyncMock(side_effect=asyncio.TimeoutError)
    proc.kill = MagicMock()

    async def fake_wait():
        await asyncio.sleep(0)

    proc.wait.side_effect = None
    proc.wait = AsyncMock(return_value=0)

    # Simulate TimeoutError from wait_for
    with patch(
        "cidrscan.scanner.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ):
        with patch(
            "cidrscan.scanner.asyncio.wait_for",
            side_effect=asyncio.TimeoutError,
        ):
            result = await _ping_once("10.0.0.1", timeout=0.01)

    assert result.alive is False
    assert result.latency_ms is None
    proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_ping_once_exception():
    with patch(
        "cidrscan.scanner.asyncio.create_subprocess_exec",
        side_effect=OSError("ping not found"),
    ):
        result = await _ping_once("10.0.0.1", timeout=1.0)

    assert result.alive is False
    assert result.latency_ms is None


# ── scan_cidr ─────────────────────────────────────────────────────────────────


def _mock_ping(alive_ips: set[str]):
    """Return a _ping_once replacement that marks given IPs as alive."""

    async def fake_ping(ip: str, timeout: float) -> ScanResult:
        return ScanResult(
            ip=ip,
            alive=ip in alive_ips,
            latency_ms=1.0 if ip in alive_ips else None,
            scanned_at=datetime.now(timezone.utc),
        )

    return fake_ping


@pytest.mark.asyncio
async def test_scan_cidr_yields_all_hosts():
    with patch("cidrscan.scanner._ping_once", new=_mock_ping(set())):
        results = [r async for r in scan_cidr("10.0.0.0/30")]

    # /30 has 2 usable hosts: .1 and .2
    assert len(results) == 2
    assert {r.ip for r in results} == {"10.0.0.1", "10.0.0.2"}


@pytest.mark.asyncio
async def test_scan_cidr_marks_alive():
    alive = {"10.0.0.1"}
    with patch("cidrscan.scanner._ping_once", new=_mock_ping(alive)):
        results = [r async for r in scan_cidr("10.0.0.0/30")]

    by_ip = {r.ip: r for r in results}
    assert by_ip["10.0.0.1"].alive is True
    assert by_ip["10.0.0.2"].alive is False


@pytest.mark.asyncio
async def test_scan_cidr_single_host():
    with patch("cidrscan.scanner._ping_once", new=_mock_ping({"192.168.0.1"})):
        results = [r async for r in scan_cidr("192.168.0.1/32")]

    assert len(results) == 1
    assert results[0].ip == "192.168.0.1"
    assert results[0].alive is True


@pytest.mark.asyncio
async def test_scan_cidr_respects_concurrency():
    """Semaphore should never allow more than `concurrency` simultaneous pings."""
    active = 0
    peak = 0

    async def counting_ping(ip: str, timeout: float) -> ScanResult:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return ScanResult(
            ip=ip,
            alive=False,
            latency_ms=None,
            scanned_at=datetime.now(timezone.utc),
        )

    with patch("cidrscan.scanner._ping_once", new=counting_ping):
        _ = [r async for r in scan_cidr("10.0.0.0/24", concurrency=10)]

    assert peak <= 10
