# Changelog

All notable changes to `aimalabs-cli` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-06-02

Initial release.

### Added
- `aima init`, `aima status`, `aima config show|set|clear` — setup and config.
- `aima voices list` with `--language`, `--provider`, `--voice-type`, `--no-active`.
- `aima campaigns list|create` — including `--field title:type:description`
  (with `:values=...` for enums), `--system-prompt`/`--extra-context` `@file`
  support, and `--from-yaml`.
- `aima leads add-test` and `aima leads upload-csv` (file or stdin, `--map`).
- `aima calls dispatch` (confirmation gated, `--yes` to skip) and
  `aima calls status` with `--poll`.
- `aima onboard` — interactive end-to-end walkthrough.
- `--json` / `--no-json` output modes, `AIMA_OUTPUT=json`, non-TTY auto-JSON.
- Env overrides: `AIMA_API_KEY`, `AIMA_BASE_URL`, `AIMA_CONFIG`.
- Stable exit codes: 0 success, 1 user error, 2 server/network, 3 config.
