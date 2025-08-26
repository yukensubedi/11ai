from .logging_utils import set_request_id

class RequestIDMiddleware:
    """
    Each request gets a unique request_id (UUID).
    - Stored in `request.id`
    - Stored in context var (for logging, exception handlers, etc.)
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Assign a unique request_id before processing the request
        request.id = set_request_id()
        return self.get_response(request)