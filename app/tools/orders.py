"""Order, return-eligibility, and initiate-return tools."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.data_loader import get_app_data
from app.state import SupportState

RETURN_WINDOW_DAYS = 30


def _data(runtime: ToolRuntime):
    return get_app_data()


@tool
def lookup_order(
    order_id: int,
    runtime: ToolRuntime[None, SupportState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Look up a Zava order by id. Returns header + line items + status."""
    data = _data(runtime)
    if data is None:
        return Command(
            update={"messages": [ToolMessage("Orders not loaded.", tool_call_id=tool_call_id)]}
        )
    order = data.orders_by_id.get(order_id)
    if not order:
        return Command(
            update={"messages": [ToolMessage(f"No order found with id {order_id}.", tool_call_id=tool_call_id)]}
        )
    return Command(
        update={
            "order_id": order_id,
            "messages": [ToolMessage(json.dumps(order, default=str), tool_call_id=tool_call_id)],
        }
    )


@tool
def list_my_orders(
    runtime: ToolRuntime[None, SupportState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    limit: int = 5,
) -> Command:
    """List the most recent orders for the currently signed-in customer.

    Use this whenever the customer asks about "my order(s)" but hasn't given
    an order id. Reads `customer_id` from the conversation state.
    """
    data = _data(runtime)
    if data is None:
        return Command(
            update={"messages": [ToolMessage("Orders not loaded.", tool_call_id=tool_call_id)]}
        )
    state = getattr(runtime, "state", None) or {}
    customer_id = state.get("customer_id") if isinstance(state, dict) else None
    if customer_id is None:
        return Command(
            update={"messages": [ToolMessage(
                "I don't know which customer this is. Ask the customer for their order id or email.",
                tool_call_id=tool_call_id,
            )]}
        )
    matching = [o for o in data.orders if o.get("customer_id") == customer_id]
    matching.sort(key=lambda o: o.get("order_date", ""), reverse=True)
    matching = matching[:limit]
    if not matching:
        return Command(
            update={"messages": [ToolMessage(
                f"No orders on file for customer {customer_id}.",
                tool_call_id=tool_call_id,
            )]}
        )
    summary_lines = [
        f"#{o['order_id']} — {o.get('order_date', '?')[:10]} — "
        f"${o.get('total_amount', 0):.2f} — {o.get('status', '?')}"
        for o in matching
    ]
    return Command(
        update={
            "messages": [ToolMessage(
                "Recent orders:\n" + "\n".join(summary_lines),
                tool_call_id=tool_call_id,
            )]
        }
    )


@tool
def get_order_status(
    order_id: int,
    runtime: ToolRuntime[None, SupportState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    """Return the shipping status string for an order. Cheaper than lookup_order when only status is needed."""
    data = _data(runtime)
    if data is None:
        return "Orders not loaded."
    order = data.orders_by_id.get(order_id)
    if not order:
        return f"No order found with id {order_id}."
    return f"Order {order_id}: status={order.get('status', 'unknown')}, " \
           f"placed={order.get('order_date', '?')}, total=${order.get('total_amount', 0):.2f}"


@tool
def check_return_eligibility(
    order_id: int,
    line_item_id: int,
    runtime: ToolRuntime[None, SupportState],
) -> str:
    """Check whether a specific line item from an order is still eligible to return."""
    data = _data(runtime)
    if data is None:
        return "Orders not loaded."
    order = data.orders_by_id.get(order_id)
    if not order:
        return f"No order found with id {order_id}."

    items = order.get("items", [])
    if not (0 <= line_item_id < len(items)):
        return f"Line item {line_item_id} is out of range for order {order_id}."

    try:
        order_dt = datetime.fromisoformat(order["order_date"].replace("Z", "+00:00"))
        if order_dt.tzinfo is None:
            order_dt = order_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return "Could not parse order date."

    age_days = (datetime.now(timezone.utc) - order_dt).days
    if age_days > RETURN_WINDOW_DAYS:
        return f"Not eligible: ordered {age_days} days ago (window is {RETURN_WINDOW_DAYS} days)."
    return f"Eligible: {RETURN_WINDOW_DAYS - age_days} days remaining in the return window."


@tool
def initiate_return(
    order_id: int,
    line_item_id: int,
    reason: str,
    runtime: ToolRuntime[None, SupportState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Create a return (RMA) record. Mutates app data — only call after explicit customer confirmation."""
    data = _data(runtime)
    if data is None:
        return Command(
            update={"messages": [ToolMessage("Orders not loaded.", tool_call_id=tool_call_id)]}
        )
    order = data.orders_by_id.get(order_id)
    if not order:
        return Command(
            update={"messages": [ToolMessage(f"No order found with id {order_id}.", tool_call_id=tool_call_id)]}
        )
    items = order.get("items", [])
    if not (0 <= line_item_id < len(items)):
        return Command(
            update={"messages": [ToolMessage(f"Line item {line_item_id} not in order.", tool_call_id=tool_call_id)]}
        )
    item = items[line_item_id]
    refund = round(item.get("unit_price", 0) * item.get("quantity", 1), 2)
    rma = {
        "return_id": f"RMA-{uuid.uuid4().hex[:8].upper()}",
        "order_id": order_id,
        "line_item_id": line_item_id,
        "reason": reason,
        "status": "requested",
        "refund_amount": refund,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data.returns.append(rma)
    return Command(
        update={
            "messages": [
                ToolMessage(
                    f"Return created: {rma['return_id']} (estimated refund ${refund:.2f}). "
                    f"Customer should ship back within 14 days.",
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )
