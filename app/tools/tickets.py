"""Ticket + CSAT tools (in-memory mutations)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from langchain.tools import ToolRuntime, tool

from app.data_loader import get_app_data
from app.state import SupportState


def _data(runtime: ToolRuntime):
    return get_app_data()


@tool
def create_support_ticket(
    summary: str,
    category: str,
    runtime: ToolRuntime[None, SupportState],
) -> str:
    """Record this conversation as a support ticket so the customer has a reference."""
    data = _data(runtime)
    if data is None:
        return "Tickets store unavailable."
    state = runtime.state if hasattr(runtime, "state") else {}
    ticket = {
        "ticket_id": f"T-{uuid.uuid4().hex[:8].upper()}",
        "customer_id": state.get("customer_id"),
        "category": category,
        "summary": summary,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data.tickets.append(ticket)
    return f"Ticket {ticket['ticket_id']} created."


@tool
def request_csat(ticket_id: str, runtime: ToolRuntime[None, SupportState]) -> str:
    """Send a CSAT survey link for the given ticket (logged in this demo)."""
    data = _data(runtime)
    if data is None:
        return "Tickets store unavailable."
    for t in data.tickets:
        if t["ticket_id"] == ticket_id:
            t["csat_requested"] = True
            return f"CSAT survey queued for {ticket_id}."
    return f"Ticket {ticket_id} not found."
