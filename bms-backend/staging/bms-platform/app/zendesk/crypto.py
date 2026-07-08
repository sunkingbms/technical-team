import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from core.exceptions import ErrorCodes, BadRequestError

logger = structlog.get_logger()

def _get_fernet_key() -> Fernet:
    """Lazy loading of the Zendesk Fernet key"""
    settings = get_settings()
    return Fernet(settings.zendesk_fernet_key.encode())

def generate_fernet_key() -> str:
    """Generates a new Zendesk Fernet key"""
    return Fernet.generate_key().decode()

def encrypt_token(plain_text: str) -> str:
    """Encrypts a plain text token using the Zendesk Fernet key"""
    if not plain_text:
        raise BadRequestError(
            message="Cannot encrypt error or empty string",
            code=ErrorCodes.ENCRYPTION_ERROR
        )
    try:
        fernet_key = _get_fernet_key()
        encrypted = fernet_key.encrypt(plain_text.encode("utf-8"))
        return encrypted.decode("utf-8")
    except Exception as e:
        logger.error("Encryption failed: ", error=str(e))
        raise BadRequestError(
            message="Encryption failed",
            code=ErrorCodes.ENCRYPTION_ERROR
        )

def decrypt_token(encrypted_text: str) -> str:
    """Decrypts an encrypted token using the Zendesk Fernet key"""
    try:
        return _get_fernet_key().decrypt(encrypted_text.encode()).decode()
    except InvalidToken:
        raise BadRequestError(message="Invalid token", code=ErrorCodes.ENCRYPTION_ERROR)