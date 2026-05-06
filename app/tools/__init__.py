"""Aggregates every @tool exposed to the agent."""
from .catalog import check_warranty, semantic_search_products
from .kb import search_help_center
from .orders import (
    check_return_eligibility,
    get_order_status,
    initiate_return,
    list_my_orders,
    lookup_order,
)
from .tickets import create_support_ticket, request_csat
from .workflow import (
    back_to_triage,
    escalate_to_human,
    lookup_customer_by_email,
    set_intent,
)

ALL_TOOLS = [
    # workflow / triage
    set_intent,
    lookup_customer_by_email,
    back_to_triage,
    escalate_to_human,
    # orders
    lookup_order,
    list_my_orders,
    get_order_status,
    check_return_eligibility,
    initiate_return,
    # catalog
    semantic_search_products,
    check_warranty,
    # kb / tech support
    search_help_center,
    # tickets
    create_support_ticket,
    request_csat,
]

__all__ = ["ALL_TOOLS"]
