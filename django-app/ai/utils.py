from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.response import Response
import logging
from .logging_utils import request_id_var

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Custom exception handler that:
    - Uses DRF's default exception handler for known errors (ValidationError, AuthenticationError, etc.)
    - Adds request_id to the response payload
    - Logs unhandled exceptions with traceback
    """
    # Let DRF build standard response if it can
    response = exception_handler(exc, context)
    rid = request_id_var.get()

    if response is not None:
        # Known/handled error (e.g., validation failed)
        logger.warning(
            "Handled error [%s] in %s: %s",
            response.status_code,
            context.get("view").__class__.__name__ if context.get("view") else "unknown",
            str(exc),
        )
        response.data = {
            "errors": response.data,   # keep DRF's field-level error details
            "status": response.status_code,
            "request_id": rid,
        }
        return response

    # Unknown/unhandled -> return generic 500
    logger.error("Unhandled error: %s", str(exc), exc_info=True)
    return Response(
        {"error": "Internal server error", "status": 500, "request_id": rid},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
