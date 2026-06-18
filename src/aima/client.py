"""Thin httpx wrapper over the /api/cli surface.

One method per endpoint in the spec. Pass dicts in, get dicts (or lists) out.
All error translation to AimaError/exit codes happens here so callers can stay
declarative.
"""

from __future__ import annotations

from typing import Any

import httpx

from . import __version__
from .config import Config
from .errors import ConfigError, ServerError, UserError

USER_AGENT = f"aimalabs-cli/{__version__}"


def _flatten_detail(detail: Any) -> str:
    """Turn a FastAPI error `detail` into a single human string.

    422 validation errors come back as a list of {loc, msg, type} objects.
    """
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = item.get("loc") or []
                loc_str = ".".join(str(p) for p in loc if p not in ("body",))
                msg = item.get("msg", "")
                parts.append(f"{loc_str}: {msg}".strip(": ").strip())
            else:
                parts.append(str(item))
        return "; ".join(p for p in parts if p)
    return str(detail)


class AimaClient:
    """HTTP client bound to a single customer's api_key + base_url."""

    def __init__(self, config: Config, *, timeout: float = 30.0) -> None:
        if not config.has_api_key:
            raise ConfigError(
                "No API key configured. Run 'aima init' to set one up."
            )
        self.config = config
        self._http = httpx.Client(
            base_url=config.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "X-API-Key": config.api_key,
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> AimaClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- core request ------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ServerError(f"Network error talking to {self.config.base_url}: {exc}") from exc

        if resp.is_success:
            if not resp.content:
                return None
            try:
                return resp.json()
            except ValueError:
                return resp.text

        self._raise_for_status(resp)

    def _raise_for_status(self, resp: httpx.Response) -> None:
        status = resp.status_code
        detail = ""
        try:
            body = resp.json()
            if isinstance(body, dict):
                detail = _flatten_detail(body.get("detail"))
            else:
                detail = str(body)
        except ValueError:
            detail = (resp.text or "").strip()

        if status == 401:
            raise UserError("Auth failed. Run 'aima init' to reconfigure.")

        if 400 <= status < 500:
            msg = detail or f"Request failed with HTTP {status}."
            raise UserError(msg)

        # 5xx
        msg = detail or f"Server error (HTTP {status})."
        raise ServerError(msg)

    # -- endpoints ---------------------------------------------------------

    def list_voices(
        self,
        *,
        language: str | None = None,
        voice_type: str | None = None,
        provider: str | None = None,
        is_active: bool | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if language is not None:
            params["language"] = language
        if voice_type is not None:
            params["voice_type"] = voice_type
        if provider is not None:
            params["provider"] = provider
        if is_active is not None:
            params["is_active"] = str(is_active).lower()
        return self._request("GET", "/api/cli/voices", params=params) or []

    def list_agents(self, *, limit: int | None = None) -> list[dict]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "/api/cli/agents", params=params) or []

    def create_agent(self, body: dict) -> dict:
        return self._request("POST", "/api/cli/agents", json=body)

    def get_agent(self, agent_id: int) -> dict:
        return self._request("GET", f"/api/cli/agents/{agent_id}")

    def update_agent(self, agent_id: int, body: dict) -> dict:
        return self._request("PATCH", f"/api/cli/agents/{agent_id}", json=body)

    def list_campaigns(
        self, *, is_active: bool | None = None, limit: int | None = None
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if is_active is not None:
            params["is_active"] = str(is_active).lower()
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "/api/cli/campaigns", params=params) or []

    def create_campaign(self, body: dict) -> dict:
        return self._request("POST", "/api/cli/campaigns", json=body)

    def update_campaign(self, campaign_id: int, body: dict) -> dict:
        return self._request("PATCH", f"/api/cli/campaigns/{campaign_id}", json=body)

    def add_test_leads(self, campaign_id: int, leads: list[dict]) -> list[dict]:
        return self._request(
            "POST",
            f"/api/cli/campaigns/{campaign_id}/test-leads",
            json={"leads": leads},
        ) or []

    def upload_csv(self, campaign_id: int, csv_content: str, mapping: dict) -> dict:
        return self._request(
            "POST",
            f"/api/cli/campaigns/{campaign_id}/leads/csv",
            json={"csv_content": csv_content, "mapping": mapping},
        )

    def dispatch(self, lead_id: int) -> dict:
        return self._request("POST", f"/api/cli/leads/{lead_id}/dispatch")

    def lead_status(self, lead_id: int) -> dict:
        return self._request("GET", f"/api/cli/leads/{lead_id}/status")

    def get_whatsapp_config(self) -> dict:
        return self._request("GET", "/api/cli/whatsapp/config")

    def create_whatsapp_connect_session(self, source: str) -> dict:
        return self._request(
            "POST",
            "/api/cli/whatsapp/connect-sessions",
            json={"source": source},
        )

    def get_whatsapp_connect_session(self, session_id: str) -> dict:
        return self._request("GET", f"/api/cli/whatsapp/connect-sessions/{session_id}")

    def register_whatsapp(self, body: dict) -> dict:
        return self._request("POST", "/api/cli/whatsapp/register", json=body)

    def list_whatsapp(self) -> list[dict]:
        return self._request("GET", "/api/cli/whatsapp") or []

    def validate_whatsapp(self, credentials_id: int) -> dict:
        return self._request("POST", f"/api/cli/whatsapp/{credentials_id}/validate")

    def list_whatsapp_templates(self, credentials_id: int) -> list[dict]:
        return self._request("GET", f"/api/cli/whatsapp/{credentials_id}/templates") or []

    def delete_whatsapp(self, credentials_id: int) -> dict:
        return self._request("DELETE", f"/api/cli/whatsapp/{credentials_id}")

    def initiate_lead(self, lead_id: int) -> dict:
        return self._request("POST", f"/api/cli/leads/{lead_id}/initiate")
