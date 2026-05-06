"""Workflow / state-transition tools: set_intent, lookup_customer, back_to_triage, escalate_to_human."""

from __future__ import annotations

from typing import Annotated

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.data_loader import get_app_data
from app.state import Intent, SupportState

# Map intent → next step. Used by `set_intent`.
_INTENT_TO_STEP = {
    "order_status": "order_lookup",
    "return_or_refund": "returns",
    "tech_support": "tech_support",
    "product_question": "product_qna",
    "billing": "resolution",
    "speak_to_human": "resolution",
    "other": "triage",
}


@tool
def set_intent(
    intent: Intent,
    runtime: ToolRuntime[None, SupportState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Record the customer's intent and hand off to the matching specialist step."""
    next_step = _INTENT_TO_STEP.get(intent, "triage")
    return Command(
        update={
            "intent": intent,
            "current_step": next_step,
            "messages": [ToolMessage(f"Routed to {next_step}.", tool_call_id=tool_call_id)],
        }
    )


@tool
def lookup_customer_by_email(
    email: str,
    runtime: ToolRuntime[None, SupportState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Find a customer by their email address."""
    data = get_app_data()
    if data is None:
        return Command(
            update={"messages": [ToolMessage("Customer database not loaded.", tool_call_id=tool_call_id)]}
        )
    customer = data.customers_by_email.get(email.strip().lower())
    if not customer:
        return Command(
            update={"messages": [ToolMessage(f"No customer found with email {email}.", tool_call_id=tool_call_id)]}
        )
    return Command(
        update={
            "customer_id": customer["customer_id"],
            "customer_email": customer["email"],
            "messages": [
                ToolMessage(
                    f"Found customer {customer.get('customer_name', '?')} (id={customer['customer_id']}).",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


@tool
def back_to_triage(
    runtime: ToolRuntime[None, SupportState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Hand control back to the triage concierge so the conversation can be wrapped up or re-routed."""
    return Command(
        update={
            "current_step": "resolution",
            "messages": [ToolMessage("Handing back to concierge.", tool_call_id=tool_call_id)],
        }
    )


@tool
def escalate_to_human(
    reason: str,
    runtime: ToolRuntime[None, SupportState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Escalate the conversation to a human support agent. Only call when the customer has explicitly confirmed."""
    return Command(
        update={
            "current_step": "resolution",
            "awaiting_escalation_confirmation": False,
            "messages": [
                ToolMessage(
                    f"🙋 Escalated to a human agent. Reason: {reason}. "
                    f"A teammate will reply by email shortly.",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )
