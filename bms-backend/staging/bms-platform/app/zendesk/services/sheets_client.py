"""
Google Sheets data fetcher.

Calls a Google Apps Script web app deployed in front of the spreadsheet.
The script URL is configurable via the GOOGLE_APPS_SCRIPT_URL env var.

Apps Script endpoint returns:
  { "headers": ["Col A", "Col B", ...], "rows": [{"Col A": "v1", ...}, ...] }
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
    Returns {"headers": [...], "rows": [{...}, ...]}
    """
    settings = get_settings()
    script_url = settings.google_apps_script_url
    if not script_url:
        raise ExternalServiceError(
            message="GOOGLE_APPS_SCRIPT_URL is not configured",
            code=ErrorCodes.ZENDESK_API_ERROR,
        )

    params = {"workbook_name": sheet_name, "sheet_id": sheet_id}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(script_url, params=params, follow_redirects=True)
        except httpx.RequestError as e:
            raise ExternalServiceError(
                message=f"Failed to reach Google Apps Script: {e}",
                code=ErrorCodes.ZENDESK_API_ERROR,
            )

    if r.status_code != 200:
        raise ExternalServiceError(
            message=f"Google Apps Script returned {r.status_code}",
            code=ErrorCodes.ZENDESK_API_ERROR,
        )

    try:
        data = r.json()
    except Exception:
        raise ExternalServiceError(
            message="Invalid response from Google Apps Script",
            code=ErrorCodes.ZENDESK_API_ERROR,
        )

    headers = data.get("headers", [])
    rows = data.get("rows", [])

    if len(headers) > MAX_COLUMNS:
        raise BadRequestError(
            message=f"Sheet has {len(headers)} columns; maximum allowed is {MAX_COLUMNS}.",
            code=ErrorCodes.BAD_REQUEST,
        )

    if not rows:
        raise BadRequestError(message="The sheet contains no data rows.", code=ErrorCodes.BAD_REQUEST)

    return {"headers": headers, "rows": rows}


async def list_sheet_tabs(sheet_id: str) -> list[str]:
    """
    Returns the list of tab names in a Google Sheet.
    Calls the Apps Script without workbook_name — the script returns {"sheets": [...]}.
    """
    settings = get_settings()
    script_url = settings.google_apps_script_url
    if not script_url:
        raise ExternalServiceError(
            message="GOOGLE_APPS_SCRIPT_URL is not configured",
            code=ErrorCodes.ZENDESK_API_ERROR,
        )

    params = {"sheet_id": sheet_id}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(script_url, params=params, follow_redirects=True)
        except httpx.RequestError as e:
            raise ExternalServiceError(
                message=f"Failed to reach Google Apps Script: {e}",
                code=ErrorCodes.ZENDESK_API_ERROR,
            )

    if r.status_code != 200:
        raise ExternalServiceError(
            message=f"Google Apps Script returned {r.status_code}",
            code=ErrorCodes.ZENDESK_API_ERROR,
        )

    try:
        data = r.json()
    except Exception:
        raise ExternalServiceError(
            message="Invalid response from Google Apps Script",
            code=ErrorCodes.ZENDESK_API_ERROR,
        )

    sheets = data.get("sheets", [])
    if not sheets:
        raise BadRequestError(message="No sheets found in the spreadsheet.", code=ErrorCodes.BAD_REQUEST)
    return sheets
