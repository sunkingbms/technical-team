import base64
import httpx
import structlog


from core.exceptions import ExternalServiceError, ErrorCodes

logger = structlog.get_logger()

class ZendeskClient:
    """
    Async HTTP client for zendesk instance, created per-request with decrypted credentials.
    """

    def __init__(self, subdomain: str, email: str, api_token: str):
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        credentials = base64.b64encode(
            f"{email}/token:{api_token}".encode()
        ).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

    async def get_ticket_fields(self) -> list[dict]:
        """Fetch all ticket fields from Zendesk instance."""
        return await self._get("/ticket_fields.json", key="ticket_fields")

    async def get_ticket_forms(self) -> list[dict]:
        """Fetch all ticket forms from Zendesk instance."""
        return await self._get("/ticket_forms.json?active=true", key="ticket_forms")

    async def get_groups(self) -> list[dict]:
        """Fetch all groups from Zendesk instance."""
        return await self._get("/groups.json?exclude_deleted=true", key="groups")

    async def get_job_status(self, job_url: str) -> dict:
        """Poll a Zendesk bulk job status URL directly (absolute URL returned by Zendesk)."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(job_url, headers=self.headers)
                if response.status_code == 404:
                    return {"job_status": {"status": "failed", "progress": 0, "results": []}}
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise ExternalServiceError(message="Zendesk job status request timed out", code=ErrorCodes.ZENDESK_API_ERROR)
        except httpx.HTTPStatusError as e:
            logger.error("zendesk_job_status_error", status_code=e.response.status_code)
            raise ExternalServiceError(
                message=f"Zendesk job status request failed: {e.response.status_code}",
                code=ErrorCodes.ZENDESK_API_ERROR,
            )

    async def bulk_create_tickets(self, tickets_payload: dict) -> dict:
        """Submit a Zendesk bulk ticket import job (up to 100 tickets per call)."""
        return await self._post("/imports/tickets/create_many.json", tickets_payload)

    async def bulk_delete_tickets(self, ticket_ids: list[int]) -> dict:
        """Submit a Zendesk bulk ticket deletion job."""
        ids_str = ",".join(str(i) for i in ticket_ids)
        return await self._delete("/tickets/destroy_many.json", params={"ids": ids_str})

    async def _get(self, path: str, key: str) -> list[dict]:
        """Generic GET used to extract the list from the named key in the response."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json().get(key, [])
        except httpx.TimeoutException:
            raise ExternalServiceError(message="Zendesk API request timed out", code=ErrorCodes.ZENDESK_API_ERROR)
        except httpx.HTTPStatusError as e:
            logger.error("zendesk_api_error", status_code=e.response.status_code, url=path)
            raise ExternalServiceError(
                message=f"Zendesk API request failed: {e.response.status_code}",
                code=ErrorCodes.ZENDESK_API_ERROR
            )

    async def _post(self, path: str, payload: dict) -> dict:
        """Generic POST returning the full parsed JSON response."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise ExternalServiceError(message="Zendesk API request timed out", code=ErrorCodes.ZENDESK_API_ERROR)
        except httpx.HTTPStatusError as e:
            logger.error("zendesk_api_error", status_code=e.response.status_code, url=path)
            raise ExternalServiceError(
                message=f"Zendesk API request failed: {e.response.status_code}: {e.response.text[:200]}",
                code=ErrorCodes.ZENDESK_API_ERROR
            )

    async def _delete(self, path: str, params: dict | None = None) -> dict:
        """Generic DELETE returning the full parsed JSON response (or {} for empty bodies)."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.delete(
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    params=params,
                )
                response.raise_for_status()
                return response.json() if response.content else {}
        except httpx.TimeoutException:
            raise ExternalServiceError(message="Zendesk API request timed out", code=ErrorCodes.ZENDESK_API_ERROR)
        except httpx.HTTPStatusError as e:
            logger.error("zendesk_api_error", status_code=e.response.status_code, url=path)
            raise ExternalServiceError(
                message=f"Zendesk API request failed: {e.response.status_code}: {e.response.text[:200]}",
                code=ErrorCodes.ZENDESK_API_ERROR
            )
