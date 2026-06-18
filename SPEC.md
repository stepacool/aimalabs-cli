# `aimalabs-cli` — implementation spec

Self-contained handoff for a future agent or engineer implementing the AIMA Labs CLI. This document is the source of truth; the backend it talks to lives in `src/entrypoints/api/cli/` of the AIMA backend repo, but you should not need to read that code — every endpoint, payload, enum, and response is inlined below.

## Goal and audience

A Python CLI named `aima`, AWS-CLI-shaped, that drives the per-customer REST surface at `/api/cli/...`. Three audiences:

1. **Humans** — operators setting up a campaign by hand.
2. **CI / scripts** — `--json` output, non-interactive.
3. **CLI-driving AI agents** (Claude Code, Cursor, OpenCode, Codex) — natural language → subcommands. The grammar of `aima <noun> <verb>` is more reliable than raw HTTP for any model.

Distributed as `aimalabs-cli` on PyPI. Install via `pipx install aimalabs-cli` or `uvx aimalabs-cli`.

The CLI lives in its own public repo — not in the backend monorepo. This spec is the only artifact carried across.

## Stack

- Python 3.11+
- `typer` (preferred) or `click` for the subcommand tree
- `httpx` for the API client (async not required — the CLI is one-shot per invocation)
- `rich` for human-readable output (tables, JSON pretty-print)
- `pydantic` v2 for response models (optional — can also use plain dicts since the API is the schema source)
- No imports from the backend. The CLI is a wire-protocol client only.

## Config

File: `~/.aima/config.json`, mode `0600`.

```json
{
  "base_url": "https://api.aimalabs.io",
  "api_key":  "api_..."
}
```

- `base_url` — defaults to `https://api.aimalabs.io`. Override only if the customer is on a self-hosted or staging deployment.
- `api_key` — required; format `api_…`. Get it from the AIMA dashboard.

The CLI returns ids only; it does not construct dashboard URLs. Dashboard slug routing is an FE concern and lives outside the backend's data model.

Env overrides take precedence over the file:

- `AIMA_API_KEY` — overrides `api_key`
- `AIMA_BASE_URL` — overrides `base_url`
- `AIMA_CONFIG` — alternative path to the config file
- `AIMA_OUTPUT=json` — forces machine-readable output

## Auth

Every request: `Authorization: Bearer ${api_key}`. The backend also accepts `X-API-Key: ${api_key}` as a fallback. Prefer `Authorization`.

If no api_key is configured, every subcommand other than `aima init`, `aima config set`, `aima config show`, and `aima --help` should exit `3` with a one-liner pointing at `aima init`.

A 401 from any endpoint surfaces as: `Auth failed. Run 'aima init' to reconfigure.` (exit `1`).

A 404 on a known-good resource (e.g., a campaign id the user clearly owns) almost always means cross-tenant access — the API hides existence on purpose by returning 404 instead of 403. The CLI should not interpret 404s; just surface them verbatim.

## Subcommand tree

Each `[composite, client-side]` row is a CLI-only orchestration; everything else is a 1:1 wrapper over a `/api/cli/` endpoint defined in the [REST API contract](#rest-api-contract) section below.

### Initial setup

| Command | Maps to | Notes |
|---|---|---|
| `aima init` | `[composite, client-side]` | Interactive first-run wizard. Prompts for `api_key`, optionally `base_url`. Validates by calling `GET /api/cli/voices`. Writes `~/.aima/config.json` with `chmod 600`. Idempotent — re-running asks whether to overwrite. |
| `aima config show` | local | Prints config with `api_key` masked as `api_…<last 4>`. Honors `--json`. |
| `aima config set <key> <value>` | local | One of `base_url`, `api_key`. |
| `aima config clear` | local | Confirms, then deletes `~/.aima/config.json`. |
| `aima status` | `[composite]` | Prints `aima config show` + result of `GET /api/cli/voices` (just "ok" or the error). Probe that the key still works. |

### Voices

| Command | Maps to |
|---|---|
| `aima voices list [--language LANG] [--provider P] [--voice-type T] [--no-active]` | `GET /api/cli/voices` with corresponding query params. |

`--no-active` sends `is_active=false`. By default `is_active=true` is sent. To list both, omit the flag entirely (the CLI can do this by not sending `is_active` at all — the backend treats omission and `true` the same, so this is a quirk; document it as "default shows active only").

### Campaigns

| Command | Maps to |
|---|---|
| `aima campaigns list [--active] [--inactive] [--limit N]` | `GET /api/cli/campaigns` |
| `aima campaigns create --title T --company-name C [--voice-id V] [--agent-name N] [--language L] [--system-prompt PATH-OR-STRING] [--extra-context PATH-OR-STRING] [--campaign-type voice\|whatsapp\|hybrid] [--whatsapp-credentials-id ID] [--template-name NAME] [--template-language LANG] [--inbound-only] [--field title:type:description] [--from-yaml FILE]` | `POST /api/cli/campaigns` |

- `--active` sends `is_active=true`; `--inactive` sends `is_active=false`; omit both to return both. They are mutually exclusive.

- `--field` may be repeated; each token is `title:type:description`. `type` ∈ `string`, `integer`, `float`, `boolean`, `date`, `datetime`, `enum`, `json`, `array`, `calendar_appointment`, `file`. For `enum`, append `:values=a,b,c`.
- `--from-yaml` reads a YAML file with the full request body (see [CampaignCreateRequest](#post-apiclicampaigns)). Mutually exclusive with explicit flags except `--title` (which still wins if both are present).
- `--system-prompt` and `--extra-context` accept either a literal string or an `@path/to/file` to read the contents from disk.

### Leads

| Command | Maps to |
|---|---|
| `aima leads add-test --campaign-id ID --lead NAME:E164 [--lead ...]` | `POST /api/cli/campaigns/{campaign_id}/test-leads` |
| `aima leads initiate <lead_id> [--yes]` | `POST /api/cli/leads/{lead_id}/initiate` — WhatsApp template send. |
| `aima leads upload-csv --campaign-id ID --file PATH --name-col COL --phone-col COL [--map FIELD=COL ...]` | `POST /api/cli/campaigns/{campaign_id}/leads/csv` (reads the file locally, posts its contents as JSON-bodied `csv_content`). |

- For `add-test`, repeat `--lead Name:+11234567890` per lead. The backend strips a leading `+` before persisting — the CLI can either pass the number through unchanged or strip it client-side; the server is tolerant.
- For `upload-csv` with `--file -`, read stdin.
- `--map FIELD=COL` is repeatable; it maps a `desired_field` title to a CSV column. The `--name-col` and `--phone-col` flags fill in the two required mapping keys.

### WhatsApp

| Command | Maps to |
|---|---|
| `aima whatsapp connect embedded\|coexistence [--no-browser] [--timeout SEC]` | `POST /api/cli/whatsapp/connect-sessions` + poll session status |
| `aima whatsapp list` | `GET /api/cli/whatsapp` |
| `aima whatsapp templates <credentials_id>` | `GET /api/cli/whatsapp/{credentials_id}/templates` |
| `aima whatsapp validate <credentials_id>` | `POST /api/cli/whatsapp/{credentials_id}/validate` |
| `aima whatsapp delete <credentials_id> [--yes]` | `DELETE /api/cli/whatsapp/{credentials_id}` |

### Calls and status

| Command | Maps to |
|---|---|
| `aima calls dispatch <lead_id>` | `POST /api/cli/leads/{lead_id}/dispatch` — places a real outbound call. **Confirm interactively unless `--yes`.** |
| `aima calls status <lead_id> [--poll] [--poll-interval 20] [--poll-timeout 300]` | `GET /api/cli/leads/{lead_id}/status` once; with `--poll`, refetch every `--poll-interval` seconds until `latest_call.ended_at` is set or `--poll-timeout` elapses. |

### Phone numbers

| Command | Maps to |
|---|---|
| `aima phones list [--limit N]` | `GET /api/cli/phones` |
| `aima phones available [--limit N]` | `GET /api/cli/phones/available` |
| `aima phones rent <phone_number_id> [--yes]` | `POST /api/cli/phones/rent` — rents from platform inventory. **Confirm interactively unless `--yes`.** |
| `aima phones release <assignment_id> [--yes]` | `DELETE /api/cli/phones/{assignment_id}` — returns number to available pool. **Confirm interactively unless `--yes`.** |

- Use `phones available` to find a `phone_number_id`, then `phones rent <id>`. After rent, `phones list` shows the `assignment_id` needed for release.
- Numbers must already exist in platform inventory (the CLI does not search or purchase from carriers).

### Composite onboarding

`aima onboard` — prompts for `voice` or `whatsapp`. Cannot run in `--json` mode.

**Voice:** init → voices → campaign → test lead → gated `calls dispatch` → poll `latest_call.ended_at`.

**WhatsApp:** credentials → validate → template list (pick #, or `0` for inbound-only) → campaign → optional test lead → gated `leads initiate` → poll `latest_conversation`.

Minimal-confirmation: only voice `calls dispatch`, WhatsApp template send, and CSV >50 rows are gated.

## Output and formatting

- Default: human-readable. Tables for lists (`rich.table.Table`), pretty key/value for single resources. Mask `api_key` as `api_…<last 4>` anywhere it appears.
- `--json` flag: emit the raw response body to stdout, nothing else. Exit code communicates success/failure.
- `AIMA_OUTPUT=json` env behaves identically to `--json`.
- Auto-detect: when stdout is not a TTY (`sys.stdout.isatty() is False`), behave as `--json`. Override with `--no-json`.

## Exit codes

- `0` — success
- `1` — user error (4xx response, bad flags, validation failure). Print the API's `detail` to stderr.
- `2` — server / network error (5xx or `httpx` failure). Print the exception summary to stderr.
- `3` — missing or invalid config (no api_key, unreadable file).

## Error model

Every 4xx/5xx from the backend is JSON with `{"detail": "..."}` (FastAPI default; for 422 validation errors, `detail` is a list of `{"loc", "msg", "type"}` objects — flatten to a single string for display). The CLI prints `detail` verbatim to stderr and exits `1` (4xx) or `2` (5xx).

---

## REST API contract

All endpoints are mounted under `/api/cli` on the backend. Every request requires `Authorization: Bearer <api_key>` (or `X-API-Key: <api_key>`). The authenticated customer is derived from the key; the CLI never sends `customer_id` in any payload.

All requests/responses are `application/json` unless noted. `int` is a JSON number; `datetime` is an ISO-8601 string in UTC (no timezone suffix — the backend emits naive UTC).

### Shared enums

```text
VoiceProvider:
  openai, google, azure, amazon_polly,
  eleven_labs, playht, murf, resemble, cartesia,
  deepgram, assemblyai, speechmatics, minimax,
  yandex, ultravox,
  coqui, openvoice, piper

VoiceType:
  per_customer, generic

CampaignType:
  whatsapp, voice, hybrid

FieldType:
  string, integer, float, boolean, date, datetime,
  calendar_appointment, json, array, enum, file

FieldInteractionType:
  always_ask, ask_if_unclear, never_ask

CallStatus:
  scheduled, initiated, ringing, in_progress,
  completed, failed, busy, no_answer, canceled

HangupCause:
  no_lead_id, dispatch_error, session_ended,
  sip_error, session_error
```

### Shared object: `Value`

```json
{ "key": "string", "value": "string" }
```

Used inside `LeadStatusOut.values` to represent extracted field values.

---

### `GET /api/cli/voices`

List voices visible to the authenticated customer (system voices + the customer's own).

**Query params** (all optional):

| Name | Type | Default | Notes |
|---|---|---|---|
| `language` | `string` | — | ISO-639-1 code, e.g. `en`, `es`. |
| `voice_type` | `VoiceType` | — | `per_customer` or `generic`. |
| `provider` | `VoiceProvider` | — | One of the enum values above. |
| `is_active` | `bool` | `true` | Pass `false` to list inactive voices. |

**Response: `200 OK` → `VoiceOut[]`** (capped at 100):

```json
[
  {
    "id": 42,
    "title": "Sarah - Friendly Sales",
    "provider": "eleven_labs",
    "voice_type": "generic",
    "languages": ["en", "es"],
    "sample_url": "https://.../sample.mp3",
    "description": "Warm, mid-30s American voice.",
    "is_system": true
  }
]
```

Any field except `id`, `languages`, and `is_system` may be `null`. `languages` is always an array (possibly empty).

---

### `GET /api/cli/campaigns`

List campaigns owned by the authenticated customer. Newest first.

**Query params** (all optional):

| Name | Type | Default | Notes |
|---|---|---|---|
| `is_active` | `bool` | — | Omit to return both active and inactive. |
| `limit` | `int` | `100` | Range `1..200`. |

**Response: `200 OK` → `CampaignListItem[]`:**

```json
[
  {
    "campaign_id": 17,
    "title": "Q2 outbound — SaaS prospects",
    "campaign_type": "voice",
    "language": "en",
    "is_active": true,
    "agent_id": 9,
    "agent_name": "Stefan",
    "company_name": "Acme Corp",
    "selected_voice_id": 42,
    "created_at": "2026-05-31T14:22:01"
  }
]
```

`agent_*`, `language`, and `selected_voice_id` may be `null` if the campaign's agent record is missing or unset.

---

### `POST /api/cli/campaigns`

Create a campaign together with its agent and its extraction fields in one atomic request.

**Request body: `CampaignCreateRequest`:**

```json
{
  "title": "Q2 outbound — SaaS prospects",
  "company_name": "Acme Corp",
  "agent_name": "Stefan",
  "selected_voice_id": 42,
  "system_prompt": null,
  "extra_context": null,
  "language": "en",
  "campaign_type": "voice",
  "is_active": true,
  "desired_fields": [
    {
      "title": "budget",
      "description": "Ask the prospect what their monthly budget is. Accept a rough range.",
      "type": "string",
      "is_required": false,
      "interaction_type": "always_ask",
      "use_calendar": false,
      "order": 1,
      "meta": null
    }
  ]
}
```

Field-by-field:

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `title` | `string` | yes | — | Human-readable campaign name. |
| `company_name` | `string` | yes | — | Used inside agent prompts. |
| `agent_name` | `string` | no | `"Stefan"` | Display name the agent introduces itself with. |
| `selected_voice_id` | `int \| null` | no | `null` | Required in practice for `campaign_type=voice` — pick from `GET /voices`. |
| `system_prompt` | `string \| null` | no | `null` | Overrides the default agent prompt. |
| `extra_context` | `string \| null` | no | `null` | Free-form context appended to the prompt. |
| `language` | `string` | no | `"en"` | ISO-639-1. |
| `campaign_type` | `CampaignType` | no | `"voice"` | `voice` for outbound dialer, `whatsapp` or `hybrid` for messaging. |
| `whatsapp_credentials_id` | `int \| null` | conditional | `null` | Required when `campaign_type` is `whatsapp` or `hybrid`. |
| `template_name` | `string \| null` | conditional | `null` | Required for outbound WhatsApp (`only_respond_to_initiated_conversations=false`). |
| `template_language` | `string \| null` | no | `"en"` | Template language code. |
| `template_kwargs` | `object \| null` | no | `null` | Template variable substitutions. |
| `only_respond_to_initiated_conversations` | `bool` | no | `false` | `true` for inbound-only (no template). Mutually exclusive with `template_name`. |
| `is_active` | `bool` | no | `true` | If `false`, the campaign won't dispatch automatically. |
| `desired_fields` | `DesiredFieldInput[]` | no | `[]` | See below. |

**`DesiredFieldInput`:**

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `title` | `string` | yes | — | Short snake_case label, e.g. `budget` or `meeting_time`. |
| `description` | `string` | yes | — | Plain-language instruction for the agent on how to obtain this value. |
| `type` | `FieldType` | no | `"string"` | See enum. |
| `is_required` | `bool` | no | `false` | If true, the agent will keep asking until extracted. |
| `interaction_type` | `FieldInteractionType` | no | `"always_ask"` | |
| `use_calendar` | `bool` | no | `false` | For `calendar_appointment` fields. |
| `order` | `int` | no | `1` | Display order. |
| `meta` | `object \| null` | no | `null` | For `type="enum"` this **must** be `{"values": ["a", "b", ...]}` — server rejects otherwise. |

**Response: `200 OK` → `CampaignCreated`:**

```json
{
  "campaign_id": 17,
  "agent_id": 9,
  "title": "Q2 outbound — SaaS prospects",
  "campaign_type": "voice",
  "desired_field_ids": [101, 102]
}
```

`agent_id` may be `null` in degenerate cases; treat it as informational.

---

### `POST /api/cli/campaigns/{campaign_id}/test-leads`

Add one or more test leads to a campaign. Does not dispatch.

**Path param:** `campaign_id: int` (must be owned by the authenticated customer; otherwise `404`).

**Request body: `TestLeadsBody`:**

```json
{
  "leads": [
    { "name": "Jane Doe", "phone_number": "+15551234567" },
    { "name": "John Roe", "phone_number": "15557654321" }
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `leads[].name` | `string` | yes | Display name shown to the agent during the call. Leading/trailing whitespace is stripped server-side. |
| `leads[].phone_number` | `string` | yes | E.164. The leading `+` is stripped server-side; either form is accepted. |

**Response: `200 OK` → `LeadOut[]`** (one per created lead, in order):

```json
[
  { "lead_id": 501, "name": "Jane Doe", "phone_number": "15551234567" },
  { "lead_id": 502, "name": "John Roe", "phone_number": "15557654321" }
]
```

---

### `POST /api/cli/campaigns/{campaign_id}/leads/csv`

Bulk-create leads from a CSV. The CLI reads the file locally and posts its contents inline.

**Path param:** `campaign_id: int`.

**Request body: `CsvUploadBody`:**

```json
{
  "csv_content": "name,phone,budget\nJane Doe,+15551234567,$500\n...",
  "mapping": {
    "name": "name",
    "phone_number": "phone",
    "values": {
      "budget": "budget"
    }
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `csv_content` | `string` | yes | Raw CSV text including the header row. |
| `mapping.name` | `string` | yes | CSV column name holding the lead's display name. |
| `mapping.phone_number` | `string` | yes | CSV column name holding the phone number. |
| `mapping.values` | `object<string,string>` | no | `desired_field_title → csv_column_name`. Empty if the CSV only has name+phone. |

Rows missing the mapped name/phone columns will still be created with empty strings for the missing values; rows with missing `values[*]` columns are silently skipped for that single value.

**Response: `200 OK` → `CsvUploadResult`:**

```json
{ "created": 312, "total_rows": 315 }
```

`created` may be less than `total_rows` if the bulk insert dedupes or filters; treat the difference as informational.

---

### `POST /api/cli/leads/{lead_id}/dispatch`

Place a real outbound call to the lead immediately. Idempotency is **not** guaranteed — every invocation dials. The CLI must require confirmation (`--yes` to skip).

**Path param:** `lead_id: int` (must belong to a campaign owned by the customer; `404` otherwise).

**Request body:** none (empty `POST`).

**Response: `200 OK` → `DispatchResult`:**

```json
{ "call_id": 9001, "lead_id": 501, "status": "initiated" }
```

`status` is a `CallStatus`. After dispatch, poll `GET /leads/{lead_id}/status` to watch it transition.

---

### `GET /api/cli/leads/{lead_id}/status`

Fetch the latest call (if any) plus any extracted field values for a lead.

**Path param:** `lead_id: int`.

**Response: `200 OK` → `LeadStatusOut`:**

```json
{
  "lead_id": 501,
  "name": "Jane Doe",
  "phone_number": "15551234567",
  "values": [
    { "key": "budget", "value": "$500/month" }
  ],
  "latest_call": {
    "call_id": 9001,
    "status": "completed",
    "hangup_cause": "session_ended",
    "recording_url": "https://.../recording.mp3",
    "transcript_text": "Agent: Hi Jane...\nLead: ...",
    "summary": "Lead expressed interest; $500/mo budget; wants demo Thursday.",
    "duration_seconds": 184,
    "initiated_at": "2026-05-31T14:22:01",
    "ended_at": "2026-05-31T14:25:05"
  },
  "latest_conversation": {
    "conversation_id": 77,
    "status": "no_response",
    "latest_message_status": "delivered",
    "latest_message_at": "2026-05-31T14:26:10"
  }
}
```

- `values` is `null` when no fields have been extracted yet; otherwise an array of `Value` objects.
- `latest_call` is `null` when no call has been placed.
- `latest_conversation` is `null` when no WhatsApp conversation exists.
- Inside `latest_call`, every field except `call_id` may be `null`. `status` is a `CallStatus`; `hangup_cause` is a `HangupCause`.
- Voice poll: terminate when `latest_call.ended_at` is set.
- WhatsApp poll: terminate when `latest_conversation.latest_message_status` is `sent` or `delivered`, or conversation status advances past `not_started` / `failed_to_start`.

---

### `POST /api/cli/leads/{lead_id}/initiate`

Send the campaign's WhatsApp template to a lead (outbound WhatsApp/hybrid only).

**Response: `200 OK` → `LeadInitiateResult`:**

```json
{ "lead_id": 501, "conversation_id": 77, "message_status": "sent", "conversation_status": "no_response" }
```

---

### `GET /api/cli/whatsapp/{credentials_id}/templates`

List **APPROVED** message templates for owned credentials.

**Response: `200 OK` → `WhatsAppTemplateItem[]`:**

```json
[{ "name": "hello_world", "language": "en", "status": "APPROVED", "category": "MARKETING" }]
```

---

### `GET /api/cli/phones`

List phone numbers rented by the authenticated customer.

**Query params:** `skip` (default `0`), `limit` (default `100`, max `1000`).

**Response: `200 OK` → `RentedPhoneNumber[]`:**

```json
[
  {
    "id": 42,
    "phone_e164": "+15551234567",
    "country_code": "1",
    "status": "assigned",
    "assignment_id": 7
  }
]
```

---

### `GET /api/cli/phones/available`

List phone numbers available to rent from platform inventory.

**Query params:** `skip`, `limit` (same as above).

**Response: `200 OK` → `PhoneNumber[]`:**

```json
[
  {
    "id": 42,
    "phone_e164": "+15551234567",
    "country_code": "1",
    "status": "available"
  }
]
```

---

### `POST /api/cli/phones/rent`

Rent an available phone number. `customer_id` is taken from the API key; it is not accepted in the body. Server sets `assignment_type: "rent"` and `monthly_price_cents: 1000`.

**Request body:**

```json
{ "phone_number_id": 42 }
```

**Response: `200 OK` → `RentPhoneResult`:**

```json
{
  "assignment_id": 7,
  "phone_number_id": 42,
  "phone_e164": "+15551234567",
  "status": "assigned",
  "assignment_type": "rent",
  "monthly_price_cents": 1000
}
```

**Errors:** `404` if the phone number does not exist; `400` if it is not `available`.

---

### `DELETE /api/cli/phones/{assignment_id}`

Release a rented phone number. Returns the number to `available` status.

**Path param:** `assignment_id: int` (must belong to the customer; `404` otherwise).

**Response: `200 OK`:**

```json
{
  "assignment_id": 7,
  "phone_e164": "+15551234567",
  "status": "ended"
}
```

**Errors:** `400` if the assignment is not `active`.

---

## API client

Hand-write a thin `AimaClient` class wrapping `httpx.Client`. Resolve `base_url` and `api_key` once at construction; raise an explicit `ConfigError` if missing. One method per endpoint above; pass dicts in, return dicts out (or pydantic models if you prefer — the schemas are stable enough for v1).

You can also codegen from `${base_url}/openapi.json` (e.g. via `datamodel-code-generator`) in a later iteration, but for v1 the contract above is authoritative and stable.

## Distribution

- PyPI package: `aimalabs-cli`. Entrypoint: `aima`.
- Console script declared in `pyproject.toml` under `[project.scripts]`.
- Provide a `--version` flag.
- Don't bundle the backend — the CLI must be installable without it.

## Out of scope for v1

- Codegen of the API client from OpenAPI — defer; hand-roll the client.
- Shell completions — `typer` provides these for free; enable but don't engineer.
- Plugin system / extension points — no.
- Bulk operations beyond CSV upload — no.
