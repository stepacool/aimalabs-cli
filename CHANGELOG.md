# Changelog

All notable changes to `aimalabs-cli` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.0] — 2026-06-19

### Added

- `aima phones list|available|rent|release` — browse platform inventory, rent outbound PSTN
  numbers, and release assignments.
- `aima usage view` — current-month voice minutes and WhatsApp leads as `used / total`.

### Changed

- Interactive prompts use [Questionary](https://questionary.readthedocs.io/) instead of Typer/Click
  `prompt`/`confirm`. List picks (channel, voice, credentials, connect mode, templates) are
  arrow-key select menus after the Rich table; inbound-only is an explicit menu item when
  templates exist.

## [0.3.0] — 2026-06-18

### Added

- `aima onboard` WhatsApp channel: connect, template picker (`0` = inbound-only), test send + poll.
- `aima whatsapp templates`, `aima leads initiate`, and WhatsApp `campaigns create` flags.

- `aima whatsapp list|connect|validate|delete` — manage WhatsApp Business accounts.
- `aima whatsapp connect` opens the dashboard embedded-signup flow in the browser
  and polls session status (no local OAuth redirect server).

## [0.2.0] — 2026-06-03

### Added

- `aima agents list|get|create|update` — manage reusable agents. `create`/`update`
  accept `--name`, `--company-name`, `--language`, `--system-prompt` (`@file`),
  and `--voice-id`.
- `aima campaigns update <id>` — `--title`, `--agent-id` (reassign agent),
  `--extra-context` (`@file`), and `--active`/`--inactive`.

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
