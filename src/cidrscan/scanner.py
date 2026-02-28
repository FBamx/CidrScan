import asyncio
import ipaddress
import sys
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from cidrscan.models import ScanResult


def _ping_args(ip: str, timeout: float) -> list[str]:
    """Build platform-appropriate ping command arguments."""
    timeout_int = max(1, int(timeout))
    if sys.platform == "win32":
        return ["ping", "-n", "1", "-w", str(timeout_int * 1000), ip]
    else:
        return ["ping", "-c", "1", "-W", str(timeout_int), ip]


async def _ping_once(ip: str, timeout: float) -> ScanResult:
    """Ping a single IP and return the result."""
    args = _ping_args(ip, timeout)
    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            returncode = await asyncio.wait_for(proc.wait(), timeout=timeout + 1)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            returncode = 1

        elapsed = (time.monotonic() - start) * 1000
        alive = returncode == 0
        return ScanResult(
            ip=ip,
            alive=alive,
            latency_ms=round(elapsed, 2) if alive else None,
            scanned_at=datetime.now(timezone.utc),
        )
    except Exception:
        return ScanResult(
            ip=ip,
            alive=False,
            latency_ms=None,
            scanned_at=datetime.now(timezone.utc),
        )


async def scan_cidr(
    cidr: str,
    *,
    concurrency: int = 100,
    timeout: float = 1.0,
) -> AsyncIterator[ScanResult]:
    """
    Scan all host IPs in a CIDR block, yielding results as they complete.

    Args:
        cidr: CIDR notation, e.g. "192.168.1.0/24".
        concurrency: Maximum number of simultaneous pings.
        timeout: Per-ping timeout in seconds.

    Yields:
        ScanResult for each IP as soon as its ping finishes.
    """
    network = ipaddress.ip_network(cidr, strict=False)
    hosts = list(network.hosts())
    if not hosts:
        # Single host (e.g. /32 or /128)
        hosts = [network.network_address]

    sem = asyncio.Semaphore(concurrency)

    async def bounded_ping(ip: str) -> ScanResult:
        async with sem:
            return await _ping_once(ip, timeout)

    tasks = [asyncio.create_task(bounded_ping(str(ip))) for ip in hosts]

    for coro in asyncio.as_completed(tasks):
        yield await coro
