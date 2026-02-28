# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install all dependencies (including dev)
uv sync --all-extras

# Run all tests
uv run pytest tests/

# Run a single test
uv run pytest tests/test_scanner.py::test_ping_once_alive

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run mypy src/

# Run the CLI
uv run cidrscan 192.168.1.0/24
uv run cidrscan 192.168.1.0/24 --tui
```

## Architecture

The project is a Python CLI tool (`cidrscan`) that ping-scans all IPs in a CIDR block.

**Data flow:**
```
cli.py (typer) → scanner.scan_cidr() → output.py / tui.py
```

**`scanner.py`** is the core engine. `scan_cidr()` is an `async` generator that yields `ScanResult` objects as pings complete (via `asyncio.as_completed`). Concurrency is controlled by `asyncio.Semaphore`. Platform-specific ping args are handled in `_ping_args()`.

**`cli.py`** is the entry point. With `--tui` it launches `CidrScanApp` from `tui.py` and returns early; otherwise it runs the async scan with a Rich progress bar and delegates rendering to `output.py`.

**`tui.py`** is a Textual `App`. The scan runs in a `@work(exclusive=True)` worker; each result is delivered to the main thread via `post_message(ResultReceived(...))`. The `_refresh_stats()` method updates the right-side stats panel after every result.

**`output.py`** is stateless — `render_json()`, `render_csv()`, `render_table()` all take `list[ScanResult]` and return strings or print directly. `output_results()` is the single dispatch function used by `cli.py`.

## Conventions

- When adding a new feature, update `README.md` to reflect it (new options, usage examples, etc.).

## Key constraints

- `Console(stderr=True)` must be created lazily inside command functions (not at module level) so that `typer`'s test runner stream substitution works correctly.
- `num_hosts` was removed in Python 3.14; use `list(network.hosts()) or [network.network_address]` instead.
- TUI tests use `app.run_test()` (Textual's async test harness). Use `app.action_*()` to invoke actions directly rather than `pilot.press()` for key bindings that may be intercepted by focused widgets.
- `pytest-asyncio` is configured with `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio` decorator (though it's harmless to include).
