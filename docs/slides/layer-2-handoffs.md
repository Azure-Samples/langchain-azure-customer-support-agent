# Layer 2 — Handoffs via `apply_step_config`

> One agent acts like 6 specialists — by swapping the system prompt and the visible tool list on every turn.

---

## Where the step lives

State has a single field that drives everything:

```python
# app/state.py
class SupportState(AgentState):
    current_step: NotRequired[Step]   # "triage" | "order_lookup" | "returns" | ...
    intent: NotRequired[Intent]
    customer_id: NotRequired[int | None]
    order_id: NotRequired[int | None]

DEFAULT_STEP: Step = "triage"
```

**Every conversation starts in `triage`** — that's the default the middleware falls back to when `current_step` is empty.

---

## The middleware that does the swap

```python
# app/middleware/steps.py

STEP_CONFIG = {
    "triage": {
        "prompt": _load_prompt("triage"),
        "tools": {"set_intent", "lookup_customer_by_email",
                  "search_help_center", "escalate_to_human"},
    },
    "returns": {
        "prompt": _load_prompt("returns"),
        "tools": {"lookup_order", "list_my_orders",
                  "check_return_eligibility", "initiate_return",
                  "back_to_triage"},
    },
    # ...4 more steps
}


@wrap_model_call
async def apply_step_config(request, handler):
    step = request.state.get("current_step") or "triage"
    config = STEP_CONFIG[step]

    # 1. swap the system prompt
    non_system = [m for m in request.messages if m.type != "system"]
    request.messages = [SystemMessage(config["prompt"]), *non_system]

    # 2. filter the tool list
    request.tools = [t for t in request.tools
                     if t.name in config["tools"]]

    return await handler(request)
```

---

## How the swap reaches the LLM

`@wrap_model_call` is an onion. Each middleware gets `(request, handler)` — `handler` is the rest of the chain, ending in the real LLM call.

```python
ModelRequest(
    model=...,        # the ChatOpenAI instance
    messages=[...],   # full history from state["messages"]
    tools=[...],      # ALL 14 tools registered with create_agent
    state=...,        # SupportState
)
```

When `await handler(request)` runs, the innermost handler does roughly:

```python
bound = request.model.bind_tools(request.tools)        # only the filtered tools
ai_message = await bound.ainvoke(request.messages)     # only the swapped prompt
return ai_message
```

So:

- **Tools become the LLM's tool schema** via `bind_tools(...)` — the provider literally only sees the filtered set and cannot emit a `tool_call` for one that isn't there.
- **Messages become the LLM input** — the new `SystemMessage` is at the head, history follows.
- **The `AIMessage` flows back out** through the middlewares (post-call side, where `validate_response` runs) and is appended to `state["messages"]`.
- **Tool calls inside that `AIMessage`** are executed by the agent's tool node from the _original_ full tool registry. The filter only affects what the LLM is _allowed to ask for_; the executor still has all 14.

---

## How `current_step` actually changes

The LLM never picks a step directly. It picks a **tool**, and three tools mutate `current_step`:

| Tool                        | Where                          | Effect                                                         |
| --------------------------- | ------------------------------ | -------------------------------------------------------------- |
| `set_intent(intent)`        | `triage`                       | maps intent → next step (`return_or_refund` → `returns`, etc.) |
| `back_to_triage()`          | any specialist                 | sets step → `resolution`                                       |
| `escalate_to_human(reason)` | any step (after user confirms) | sets step → `resolution`                                       |

Each returns a `Command(update={"current_step": ...})`. LangGraph applies it, checkpoints state, and on the next turn `apply_step_config` reads the new value.

---

## Mental model

> The agent is built once. Tools are registered once. The middleware doesn't add tools to the agent — it shows the LLM a _subset_ of the already-registered tools on each turn, and swaps the system prompt for that turn. Everything else (state updates, tool execution, message accumulation) is the standard LangGraph agent loop.
