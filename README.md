# langchain-azure-customer-support-agent

A Fin-style customer support agent built with **LangChain v1** on **Azure OpenAI Responses API**, deployed in a single Azure Container App. Optimised aggressively for fast `azd up`.

- **Pattern:** Handoffs (state-machine middleware) — see [LangChain docs](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs-customer-support).
- **Models:** `gpt-5.4-mini` (main support driver) + `gpt-5-nano` (cheap utility model for refine / validate / summarise — **15× cheaper input** than the main).
- **Reliability layer:** Fin-inspired refine → retrieve → optional rerank → generate → validate.
- **No Postgres, no MCP server.** Help-center search is in-memory NumPy cosine over pre-computed embeddings. Tools are in-process Python `@tool`s called via Responses-API function calling.
- **One Container App.** AOAI + ACR + Container Apps env + Log Analytics + App Insights. That's it.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Container App: chat                                         │
│   Starlette + lifespan                                       │
│    create_agent(                                             │
│      model = ChatOpenAI(use_responses_api=True),             │
│      tools = ALL_TOOLS,                                      │
│      middleware = [                                          │
│        refine_query,        ← cheap nano LLM                 │
│        apply_step_config,   ← Handoffs (6 steps)             │
│        validate_response,   ← cheap nano groundedness check  │
│        SummarizationMiddleware,                              │
│      ],                                                      │
│      state_schema   = SupportState,                          │
│      checkpointer   = InMemorySaver(),                       │
│    )                                                         │
│   In-memory data: customers, orders, products,               │
│                   warranty_terms, kb_articles + kb_embeddings│
└──────────────────────────────────────────────────────────────┘
                ↓ Entra ID, no API key
┌──────────────────────────────────────────────────────────────┐
│  Azure OpenAI:  gpt-5.4-mini, gpt-5-nano,                    │
│                 text-embedding-3-small                       │
└──────────────────────────────────────────────────────────────┘
```

### State machine (Handoffs)

| Step               | Tools                                                                               |
| ------------------ | ----------------------------------------------------------------------------------- |
| `triage` (default) | `set_intent`, `lookup_customer_by_email`, `search_help_center`, `escalate_to_human` |
| `order_lookup`     | `lookup_order`, `get_order_status`, `back_to_triage`                                |
| `returns`          | `lookup_order`, `check_return_eligibility`, `initiate_return`, `back_to_triage`     |
| `tech_support`     | `search_help_center`, `check_warranty`, `back_to_triage`                            |
| `product_qna`      | `semantic_search_products`, `check_warranty`, `back_to_triage`                      |
| `resolution`       | `create_support_ticket`, `request_csat`, `escalate_to_human`                        |

Tool-driven transitions: state-mutating tools return `Command(update={"current_step": ...})`. See [app/middleware/steps.py](app/middleware/steps.py).

### Validation modes (`VALIDATION_MODE`)

When the model produces a tool-free reply in `tech_support` or `product_qna`, the validate middleware runs a cheap groundedness classifier on the nano model. Behaviour:

- `advisory` — log only, ship the reply as-is.
- `rewrite` (**default**) — replace the reply with _"I couldn't find that in our help center. Would you like me to connect you with a human?"_ and surface yes/no suggestion chips. The next turn's "yes" triggers `escalate_to_human`. **No silent escalations.**
- `escalate` — call `escalate_to_human` immediately.

## Deploy

```bash
az login
azd up
```

Targets `~3-4 minutes` cold from `azd up` to working chat:

| Phase                                  | ~Time |
| -------------------------------------- | ----- |
| RG + identities + ACR + monitoring     | 30s   |
| AOAI + 3 deployments (main/nano/embed) | 90s   |
| Container Apps env                     | 60s   |
| Image build (uv + BuildKit cache)      | 45s   |
| Container App + first revision         | 45s   |

After `azd up`, browse to the URL printed in `CHAT_URL`.

## Local dev

```bash
cp .env.example .env       # set AZURE_OPENAI_ENDPOINT
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
az login                   # for DefaultAzureCredential
uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Data

All data is committed and loaded into memory at startup:

| File                       | What                                                           |
| -------------------------- | -------------------------------------------------------------- |
| `data/customers.json`      | 50 mock customers                                              |
| `data/orders.json`         | 200 mock orders                                                |
| `data/products.json`       | 30 representative SKUs (with `description_embedding`)          |
| `data/warranty_terms.json` | 4 category-level warranty rules                                |
| `data/kb_articles.json`    | 12 synthetic Zava help-center articles                         |
| `data/kb_embeddings.npy`   | NumPy array (12, 1536) — generated on first startup if missing |

To regenerate from scratch (requires the [`langchain-agent-python`](https://github.com/Azure-Samples/langchain-agent-python) repo cloned as a sibling):

```bash
cd data
python generate_sample_data.py                        # local AOAI endpoint computes embeddings
python generate_sample_data.py --no-embeddings        # skip; runtime will compute on first start
```

## What's different from `langchain-agent-python`?

|             | `langchain-agent-python`  | **this repo**                            |
| ----------- | ------------------------- | ---------------------------------------- |
| Pattern     | Single agent + MCP server | Handoffs state machine, in-process tools |
| Database    | Postgres + pgvector       | None — JSON + NumPy in memory            |
| Services    | 2 Container Apps          | 1 Container App                          |
| Cold deploy | ~10-15 min (Postgres)     | ~3-4 min                                 |
| Models      | gpt-5-mini                | gpt-5.4-mini + gpt-5-nano (cost-tier'd)  |
| Reliability | none                      | refine + validate + summarise            |

The `langchain-agent-python` template demonstrates the MCP-server pattern; **this** template demonstrates the cheapest, fastest support agent that still ships production-grade reliability primitives.

## Tests

```bash
pip install -e .[dev]
pytest -q
```

The integration tests that actually call AOAI are skipped unless `AZURE_OPENAI_ENDPOINT` is set.

## Credits

- Architecture inspired by [Fin's AI Engine](https://fin.ai/ai-engine) (5-phase: refine → retrieve → rerank → generate → validate).
- "Do you really need a Vector Search Database?" — Fin's blog informed the in-memory NumPy decision.
- LangChain customer-support [handoffs tutorial](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs-customer-support).
- Bicep / azd shape baselined on [`Azure-Samples/langchain-azure-openai-starter`](https://github.com/Azure-Samples/langchain-azure-openai-starter).

LangChain blue (#1F4FFF) UI is design-inspired only — not officially endorsed.
