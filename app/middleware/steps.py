"""Step configuration middleware (Handoffs pattern).

For each `current_step` we declare:
  - `system_prompt`: which prompt file's contents to inject.
  - `tools`: which tool names the model is allowed to see in this step.

Per the LangChain customer-support handoffs tutorial, this is implemented
as a `@wrap_model_call` middleware that intercepts each model invocation
and rewrites the request based on `state["current_step"]`.

Reference: https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs-customer-support
"""

from __future__ import annotations

from pathlib import Path

from langchain.agents.middleware import ModelRequest, wrap_model_call
from langchain_core.messages import SystemMessage

from app.state import DEFAULT_STEP, Step, SupportState

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text().strip()


# Step → which tool names the model sees.
STEP_CONFIG: dict[Step, dict] = {
    "triage": {
        "prompt": _load_prompt("triage"),
        "tools": {
            "set_intent",
            "lookup_customer_by_email",
            "search_help_center",  # FAQ shortcut
            "escalate_to_human",
        },
    },
    "order_lookup": {
        "prompt": _load_prompt("order_lookup"),
        "tools": {
            "lookup_order",
            "list_my_orders",
            "get_order_status",
            "back_to_triage",
        },
    },
    "returns": {
        "prompt": _load_prompt("returns"),
        "tools": {
            "lookup_order",
            "list_my_orders",
            "check_return_eligibility",
            "initiate_return",
            "back_to_triage",
        },
    },
    "tech_support": {
        "prompt": _load_prompt("tech_support"),
        "tools": {
            "search_help_center",
            "check_warranty",
            "back_to_triage",
        },
    },
    "product_qna": {
        "prompt": _load_prompt("product_qna"),
        "tools": {
            "semantic_search_products",
            "check_warranty",
            "back_to_triage",
        },
    },
    "resolution": {
        "prompt": _load_prompt("resolution"),
        "tools": {
            "create_support_ticket",
            "request_csat",
            "escalate_to_human",
        },
    },
}


@wrap_model_call
async def apply_step_config(request: ModelRequest, handler):
    """Inject the step-specific system prompt and filter the tool list."""
    state: SupportState = request.state  # type: ignore[assignment]
    step: Step = state.get("current_step") or DEFAULT_STEP  # type: ignore[assignment]
    config = STEP_CONFIG.get(step, STEP_CONFIG["triage"])

    # Inject system prompt at the head of the messages list (replace any prior).
    system_msg = SystemMessage(content=config["prompt"])
    msgs = [m for m in request.messages if not (hasattr(m, "type") and m.type == "system")]
    request.messages = [system_msg, *msgs]

    # Filter tools: keep only the ones allowed for this step.
    allowed = config["tools"]
    request.tools = [t for t in request.tools if getattr(t, "name", None) in allowed]
    return await handler(request)
