from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    original = response.data
    response.data = {
        "error": {
            "code": error_code(response.status_code),
            "message": error_message(original),
            "details": original,
        }
    }
    return response


def error_code(status_code):
    return {
        400: "VALIDATION_ERROR",
        401: "AUTHENTICATION_REQUIRED",
        403: "PERMISSION_DENIED",
        404: "NOT_FOUND",
        429: "RATE_LIMITED",
    }.get(status_code, "REQUEST_FAILED")


def error_message(details):
    if isinstance(details, dict):
        detail = details.get("detail")
        if detail is not None:
            return str(detail)
        first_value = next(iter(details.values()), "Request could not be completed.")
        if isinstance(first_value, list) and first_value:
            return str(first_value[0])
        return str(first_value)
    if isinstance(details, list) and details:
        return str(details[0])
    return str(details)
