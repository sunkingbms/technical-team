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
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)
        
class BadRequestError(ApplicationException):
    """Exception raised for bad requests (400)"""
    def __init__(self, message: str = "Bad Request", error_code: str = "BAD_REQUEST"):
        super().__init__(message, 400, error_code)
        
class ForbiddenError(ApplicationException):
    def __init__(self, message: str = "Permission Denied", error_code: str = "PERMISSION_DENIED"):
        super().__init__(message, 403, error_code)
        
class UnauthorizedError(ApplicationException):
    def __init__(self, resource_name: str, action: str, reason: str = "UNAUTHORIZED_ACCESS"):
        super().__init__(
            message = f"Unauthorized to {action} {resource_name}",
            status_code = 401,
            error_code = reason,
        )
        
class NotFoundError(ApplicationException):
    def __init__(self, resource_name: str, reason: str = "RESOURCE_NOT_FOUND"):
        super().__init__(
            message = f"{resource_name} not found",
            status_code = 404,
            error_code = reason,
        )
        
class ConflictError(ApplicationException):
    def __init__(self, resource_name: str, reason: str = "DUPLICATES_VALUES"):
        super().__init__(
            message = f"{resource_name} has duplicate values",
            status_code = 409,
            error_code = reason,
        )