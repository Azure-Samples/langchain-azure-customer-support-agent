"""SupportState: extends LangChain v1 AgentState with handoff metadata.

The state machine in `app/middleware/steps.py` reads `current_step` to pick
the right system prompt + tool subset. State-mutating tools return
`Command(update={...})` to transition.
"""

from __future__ import annotations

from typing import Literal, NotRequired

from langchain.agents import AgentState

Step = Literal[
    "triage",
    "order_lookup",
    "returns",
    "tech_support",
    "product_qna",
    "resolution",
]

Intent = Literal[
    "order_status",
    "return_or_refund",
    "tech_support",
    "product_question",
    "billing",
    "speak_to_human",
    "other",
]


class SupportState(AgentState):
    """Conversation + workflow state for the support agent."""

    # Workflow
    current_step: NotRequired[Step]
    intent: NotRequired[Intent]

    # Customer context (set by triage)
    customer_id: NotRequired[int | None]
    customer_email: NotRequired[str | None]

    # Order context (set by order_lookup / returns)
    order_id: NotRequired[int | None]

    # Validation: list of doc_ids retrieved on this turn (used by validate middleware)
    last_retrieved_docs: NotRequired[list[str]]

    # Set when validation rewrote the response and the user's next yes/no
    # answer should be interpreted as confirming escalation.
    awaiting_escalation_confirmation: NotRequired[bool]


DEFAULT_STEP: Step = "triage"
