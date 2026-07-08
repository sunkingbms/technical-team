import base64
import httpx
import structlog


from core.exceptions import  ExternalServiceError, ErrorCodes

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
    
    
    async def _get(self, path: str, key: str) -> list[dict]:
        """Generic GET used to extracts the list from the named key in the response."""
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