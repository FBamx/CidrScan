from dataclasses import dataclass
from datetime import datetime


@dataclass
class ScanResult:
    ip: str
    alive: bool
    latency_ms: float | None
    scanned_at: datetime
