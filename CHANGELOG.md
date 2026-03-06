# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-28

### Added
- Initial release
- Async concurrent ping scanning with configurable concurrency and timeout
- Three output formats: table (with colors), JSON, CSV
- Interactive TUI mode with live results table and statistics panel
- `--alive-only` flag to filter results
- `--tui` flag to launch interactive terminal UI
- `--version` flag to show version information
- Cross-platform support (macOS, Linux, Windows)
- Exit code 0 if any host alive, 1 if all dead (for scripting)
- Real-time progress bar during scan
- Export to CSV from TUI (press `e`)

[0.1.0]: https://github.com/yourname/cidrscan/releases/tag/v0.1.0
