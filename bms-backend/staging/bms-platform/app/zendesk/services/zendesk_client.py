"""
Thin async HTTP client for the Zendesk API.
All calls use Basic auth: base64(email/token:access_token).
"""
import base64

import httpx
import structlog

from core.exceptions import ErrorCodes, ExternalServiceError

logger = structlog.get_logger()

TIMEOUT = httpx.Timeout(30.0)


def _auth_header(email: str, access_token: str) -> dict:
    creds = base64.b64encode(f"{email}/token:{access_token}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


class ZendeskClient:
    def __init__(self, subdomain: str, email: str, access_token: str):
        self._base = f"https://{subdomain}/api/v2"
        self._headers = _auth_header(email, access_token)

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{self._base}{path}", headers=self._headers, params=params)
        if r.status_code != 200:
            logger.warning("zendesk_api_error", path=path, status=r.status_code)
            raise ExternalServiceError(
                f"Zendesk API error {r.status_code}: {r.text[:200]}",
                ErrorCodes.ZENDESK_API_ERROR,
            )
        return r.json()

    async def _post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(f"{self._base}{path}", headers=self._headers, json=payload)
        if r.status_code not in (200, 201):
            raise ExternalServiceError(
                f"Zendesk API error {r.status_code}: {r.text[:200]}",
                ErrorCodes.ZENDESK_API_ERROR,
            )
        return r.json()

    async def _delete(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.delete(f"{self._base}{path}", headers=self._headers, params=params)
        if r.status_code not in (200, 204):
            raise ExternalServiceError(
                f"Zendesk API error {r.status_code}: {r.text[:200]}",
                ErrorCodes.ZENDESK_API_ERROR,
            )
        return r.json() if r.content else {}

    # ── resource fetchers ─────────────────────────────────────────────────────

    async def get_ticket_fields(self) -> list[dict]:
        data = await self._get("/ticket_fields.json")
        return data.get("ticket_fields", [])

    async def get_ticket_forms(self) -> list[dict]:
        data = await self._get("/ticket_forms.json", params={"active": "true"})
        return data.get("ticket_forms", [])

    async def get_groups(self) -> list[dict]:
        data = await self._get("/groups.json", params={"exclude_deleted": "true"})
        return data.get("groups", [])

    async def get_job_status(self, job_url: str) -> dict:
        """Poll a Zendesk bulk job status URL directly."""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(job_url, headers=self._headers)
        if r.status_code == 404:
            return {"job_status": {"status": "failed", "progress": 0, "results": []}}
        if r.status_code != 200:
            raise ExternalServiceError(
                f"Zendesk job status error {r.status_code}",
                ErrorCodes.ZENDESK_API_ERROR,
            )
        return r.json()

    async def bulk_create_tickets(self, tickets_payload: dict) -> dict:
        return await self._post("/imports/tickets/create_many.json", tickets_payload)

    async def bulk_delete_tickets(self, ticket_ids: list[int]) -> dict:
        ids_str = ",".join(str(i) for i in ticket_ids)
        return await self._delete("/tickets/destroy_many.json", params={"ids": ids_str})
