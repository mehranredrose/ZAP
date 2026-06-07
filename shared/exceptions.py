import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Standardize error response format across all services.
    Returns: {"error": {"code": "...", "message": "...", "detail": [...]}}
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_payload = {
            "error": {
                "code": _get_error_code(response.status_code),
                "message": _format_message(response.data),
                "detail": response.data if isinstance(response.data, list) else [],
            }
        }
        response.data = error_payload
        return response

    # Unhandled exception — log it, return 500
    logger.exception("Unhandled exception in view", exc_info=exc)
    return Response(
        {"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _get_error_code(status_code: int) -> str:
    codes = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        429: "rate_limited",
        500: "internal_error",
    }
    return codes.get(status_code, "error")


def _format_message(data) -> str:
    if isinstance(data, dict):
        for key in ("detail", "non_field_errors", "message"):
            if key in data:
                val = data[key]
                return val[0] if isinstance(val, list) else str(val)
        first_val = next(iter(data.values()), "")
        return first_val[0] if isinstance(first_val, list) else str(first_val)
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data)