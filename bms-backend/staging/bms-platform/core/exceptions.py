# Implementation of custom exceptions

class AppError(Exception):
    """
    Base class for all application domain-level exceptions
    Responsibilities of this class are below:
      1- Provide a human-readable message for logging and API;s response
      2- Provide a machine readable code for the API consumers to handle programmatically
    """
    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(self.message)
        
class BadRequestError(AppError):
    """Exception raised for bad requests (400)"""
    pass
        
class ForbiddenError(AppError):
    """Exception raised for forbidden requests (403)"""
    pass
        
class UnauthorizedError(AppError):
    """Exception raised for unauthorized requests (401)"""
    pass
        
class NotFoundError(AppError):
    """Exception raised for not found requests (404)"""
    pass
        
class ConflictError(AppError):
    """Exception raised for conflict requests (409)"""
    pass
        
class InternalServerError(AppError):
    """Exception raised for internal server errors (500)"""
    pass

class ServiceUnavailableError(AppError):
    """Exception raised for service unavailable errors (503)"""
    pass

class ValidationError(AppError):
    """Exceptions raise when failed to meet business rules"""
    pass

class ExternalServiceError(AppError):
    """Exception raised when a third party system integrated to our API fails"""
    pass

class ErrorCodes:
    """Human readable error codes for the API consumers to handle programmatically
    """
    
    # Auth
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    UNAUTHORIZED_ERROR = "UNAUTHORIZED_ERROR"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    TOKEN_NOT_FOUND = "TOKEN_NOT_FOUND"
    TOKEN_INVALID = "TOKEN_INVALID"
    
    # User
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_EMAIL_ALREADY_EXISTS = "USER_EMAIL_ALREADY_EXISTS"
    
    # RBAC
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ROLE_NOT_FOUND = "ROLE_NOT_FOUND"
    ROLE_ALREADY_EXISTS = "ROLE_ALREADY_EXISTS"
    
    # Zendesk
    INSTANCE_NOT_FOUND = "ZENDESK_INSTANCE_NOT_FOUND"
    INSTANCE_ALREADY_EXISTS = "ZENDESK_INSTANCE_ALREADY_EXISTS"
    API_KEY_NOT_FOUND = "API_KEY_NOT_FOUND"
    ZENDESK_API_ERROR = "ZENDESK_API_ERROR"
    NO_ACTIVE_API_KEY = "NO_ACTIVE_API_KEY"
    ENCRYPTION_ERROR = "ENCRYPTION_ERROR"
    
    # Task
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    
    # Generic
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BAD_REQUEST = "BAD_REQUEST"