"""
Google Sheets data fetcher.

Calls the same Google Apps Script web app used by the original PHP app.
The script URL is configurable via GOOGLE_APPS_SCRIPT_URL env var.

Apps Script endpoint returns:
  { "headers": ["Col A", "Col B", ...], "rows": [["v1","v2",...], ...] }
"""
import httpx
import structlog

from app.config import get_settings
from core.exceptions import BadRequestError, ErrorCodes, ExternalServiceError

logger = structlog.get_logger()

TIMEOUT = httpx.Timeout(30.0)
MAX_COLUMNS = 20


async def fetch_sheet_data(sheet_id: str, sheet_name: str) -> dict:
    """
    Returns {"headers": [...], "rows": [[...], ...]}
    """
    settings = get_settings()
    script_url = settings.google_apps_script_url

    params = {"workbook_name": sheet_name, "sheet_id": sheet_id}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(script_url, params=params, follow_redirects=True)
        except httpx.RequestError as e:
            raise ExternalServiceError(
                f"Failed to reach Google Apps Script: {e}",
                ErrorCodes.ZENDESK_API_ERROR,
            )

    if r.status_code != 200:
        raise ExternalServiceError(
            f"Google Apps Script returned {r.status_code}",
            ErrorCodes.ZENDESK_API_ERROR,
        )

    try:
        data = r.json()
    except Exception:
        raise ExternalServiceError("Invalid response from Google Apps Script", ErrorCodes.ZENDESK_API_ERROR)

    headers = data.get("headers", [])
    rows = data.get("rows", [])

    if len(headers) > MAX_COLUMNS:
        raise BadRequestError(
            f"Sheet has {len(headers)} columns; maximum allowed is {MAX_COLUMNS}.",
            ErrorCodes.BAD_REQUEST,
        )

    if not rows:
        raise BadRequestError("The sheet contains no data rows.", ErrorCodes.BAD_REQUEST)

    return {"headers": headers, "rows": rows}
