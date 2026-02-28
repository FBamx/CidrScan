from datetime import datetime, timezone

from cidrscan.models import ScanResult
from cidrscan.output import render_csv, render_json, render_table


def _make(ip: str, alive: bool, latency: float | None = None) -> ScanResult:
    return ScanResult(
        ip=ip,
        alive=alive,
        latency_ms=latency,
        scanned_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


RESULTS = [
    _make("10.0.0.1", alive=True, latency=3.5),
    _make("10.0.0.2", alive=False),
    _make("10.0.0.3", alive=True, latency=1.2),
]


# ── JSON ──────────────────────────────────────────────────────────────────────


def test_render_json_all():
    import json

    data = json.loads(render_json(RESULTS))
    assert len(data) == 3
    assert data[0]["ip"] == "10.0.0.1"
    assert data[0]["alive"] is True
    assert data[0]["latency_ms"] == 3.5


def test_render_json_alive_only():
    import json

    data = json.loads(render_json(RESULTS, alive_only=True))
    assert len(data) == 2
    assert all(d["alive"] for d in data)


def test_render_json_dead_host_has_null_latency():
    import json

    data = json.loads(render_json(RESULTS))
    dead = next(d for d in data if not d["alive"])
    assert dead["latency_ms"] is None


# ── CSV ───────────────────────────────────────────────────────────────────────


def test_render_csv_header():
    text = render_csv(RESULTS)
    first_line = text.splitlines()[0]
    assert first_line == "ip,alive,latency_ms,scanned_at"


def test_render_csv_row_count():
    text = render_csv(RESULTS)
    # header + 3 data rows
    assert len(text.splitlines()) == 4


def test_render_csv_alive_only_row_count():
    text = render_csv(RESULTS, alive_only=True)
    # header + 2 alive rows
    assert len(text.splitlines()) == 3


def test_render_csv_empty_latency_for_dead():
    text = render_csv(RESULTS)
    dead_row = [line for line in text.splitlines() if "10.0.0.2" in line][0]
    parts = dead_row.split(",")
    assert parts[2] == ""  # latency_ms empty for dead host


# ── table (smoke test — just check it doesn't raise) ─────────────────────────


def test_render_table_smoke(capsys):
    render_table(RESULTS)  # should not raise


def test_render_table_alive_only_smoke():
    render_table(RESULTS, alive_only=True)
