# Layer 1 — Primary agent + 4 middlewares

> Every call to the LLM is wrapped by all 4 middlewares, in order.

---

## The middleware chain

| #     | Middleware                | Phase         | Model        | What it does                                                                                                                        |
| ----- | ------------------------- | ------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| **1** | `refine_query`            | pre-call      | `gpt-5-nano` | Rewrites a vague user message into an explicit query and appends a clarifying `HumanMessage` to `request.messages`.                 |
| **2** | `apply_step_config`       | pre-call      | —            | Reads `state["current_step"]`, swaps the system prompt, and filters `request.tools` to that step's allowlist. _(zoom in: Layer 2)_  |
| **3** | `validate_response`       | **post-call** | `gpt-5-nano` | Groundedness-checks the `AIMessage`. In `rewrite` mode, replaces hallucinated content with the safe `ASK_BEFORE_ESCALATE` template. |
| **4** | `SummarizationMiddleware` | pre-call      | `gpt-5-nano` | LangChain built-in. When history > **4000 tokens**, condenses older turns into one summary message and keeps recent turns verbatim. |

---

## Example — refine in action

> **User:** "where is it?"
>
> **After `refine_query`:** "What is the status of order #123?"

---

## Key ideas

- **Pre-call** middlewares mutate `request.messages` / `request.tools` _before_ the LLM runs.
- **Post-call** middleware (`validate_response`) inspects and can rewrite the `AIMessage` _after_ the LLM responds.
- All middlewares are `async` and call `await handler(request)` to chain to the next layer — that's what makes them composable.

---

## Execution order

```text
user msg  →  refine  →  apply_step_config  →  [ LLM ]  →  validate  →  reply
                                                              ↑
                                       summarise (kicks in on long histories)
```
