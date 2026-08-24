"""Typed failures for the checkout desk.

ADK matches retry_config.exceptions by exception CLASS NAME, not by
isinstance. A subclass of a listed class is NOT retried. So every class
here is concrete and gets listed explicitly in RETRYABLE below. Do not
introduce a shared base class and list only the base: it will silently
never match.
"""

from google.adk.workflow import NodeTimeoutError


class WarehouseUnavailable(Exception):
    """Warehouse API returned 5xx or refused the connection. Safe to retry."""


class PaymentGatewayUnavailable(Exception):
    """Gateway returned 5xx or timed out. Safe to retry with the same
    idempotency key, never without one."""


class PaymentDeclined(Exception):
    """The card was declined. Retrying will decline again. Do not retry."""


class OutOfStock(Exception):
    """There is no stock. Retrying will not create any. Do not retry."""


class CircuitOpen(Exception):
    """We refused to call a dependency we believe is down. Do not retry:
    the whole point was to stop generating load."""


# The exact list ADK checks against. Names, not ancestry.
RETRYABLE = [
    WarehouseUnavailable,
    PaymentGatewayUnavailable,
    NodeTimeoutError,
    "ServerError",  # google.genai 5xx
    "ClientError",  # google.genai 4xx, which includes 429 rate limits
]
