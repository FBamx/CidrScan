# CidrScan

Ping-scan every IP in a CIDR block from the command line. Results stream in as
they arrive — no waiting for the whole range to finish.

## Features

- **Async & fast** — concurrent pings via `asyncio`, configurable concurrency
- **Real-time progress** — live progress bar on stderr while data flows to stdout
- **Three output formats** — colour table, JSON, CSV
- **Interactive TUI** — full terminal UI with live results table and stats panel
- **Scriptable** — exits `0` if any host is alive, `1` if all are dead
- **Cross-platform** — macOS, Linux, Windows

## Installation

Requires Python 3.11+.

```bash
pip install cidrscan
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv tool install cidrscan
```

## Usage

```
cidrscan [OPTIONS] CIDR
```

### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--concurrency` | `-c` | `100` | Max simultaneous pings |
| `--timeout` | `-t` | `1.0` | Per-ping timeout (seconds) |
| `--output` | `-o` | `table` | Output format: `table` \| `json` \| `csv` |
| `--alive-only` | `-a` | off | Only show alive hosts |
| `--out` | `-f` | — | Write results to file instead of stdout |
| `--no-summary` | | off | Suppress the summary line |
| `--tui` | `-u` | off | Launch interactive TUI |

### Examples

Scan a /24, show only alive hosts:

```bash
cidrscan 192.168.1.0/24 --alive-only
```

Scan quickly with higher concurrency and a tighter timeout:

```bash
cidrscan 10.0.0.0/16 -c 500 -t 0.5
```

Output as JSON and pipe to `jq`:

```bash
cidrscan 10.0.0.0/24 --output json --no-summary | jq '[.[] | select(.alive)]'
```

Save CSV results to a file:

```bash
cidrscan 172.16.0.0/12 --output csv --out results.csv
```

Use in a shell script (exit code reflects liveness):

```bash
if cidrscan 192.168.1.1/32 --no-summary > /dev/null 2>&1; then
    echo "host is up"
fi
```

Launch the interactive TUI:

```bash
cidrscan 192.168.1.0/24 --tui
```

TUI key bindings: `s` scan, `e` export CSV, `q` quit.

### Sample output

```
 IP Address        Status   Latency (ms)   Scanned At
 192.168.1.1       alive           1.23   2024-06-01 12:00:01 UTC
 192.168.1.2       dead               -   2024-06-01 12:00:01 UTC
 192.168.1.3       alive           0.87   2024-06-01 12:00:02 UTC
 ...

Summary: 42/254 alive, avg latency 1.1 ms
```

## Development

```bash
git clone https://github.com/yourname/cidrscan
cd cidrscan
uv sync --all-extras
uv run pytest
```

Lint and type-check:

```bash
uv run ruff check src/ tests/
uv run mypy src/
```

## License

MIT
