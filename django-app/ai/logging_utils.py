import contextvars
import uuid

# Context variable to store request ID
request_id_var = contextvars.ContextVar("request_id", default="-")

def set_request_id():
    """
    Generate a new UUID for the request and store it in the context.
    Returns the request_id so it can also be attached to the request object.
    """
    rid = str(uuid.uuid4())
    request_id_var.set(rid)
    return rid