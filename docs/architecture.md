# Architecture

The deployed sample is a single Azure Container App backed by Azure OpenAI, ACR, and monitoring. All conversation data is in-memory; there is no database.

```mermaid
flowchart LR
    user["User<br/>(browser)"]
    subgraph aca["Azure Container App · Starlette + LangGraph"]
      direction TB
      agent["create_agent · LangChain v1<br/>gpt-5.4-mini · Responses API"]
      subgraph mw["Middleware chain (wraps every model call)"]
        direction LR
        m1["refine<br/>(nano)"] --> m2["apply_step_config<br/>(handoffs)"] --> m3["validate<br/>(nano)"] --> m4["summarise<br/>(nano)"]
      end
      tools["14 in-process @tools<br/>workflow · orders · returns<br/>knowledge · wrap-up"]
      data["In-memory data<br/>customers · orders · products<br/>KB articles + NumPy embeddings"]
      agent --- mw
      agent --- tools
      tools --- data
    end
    aoai["Azure OpenAI<br/>gpt-5.4-mini · gpt-5-nano<br/>text-embedding-3-small"]
    obs["Log Analytics<br/>+ App Insights"]
    acr["Azure Container<br/>Registry"]

    user -->|HTTPS / SSE| aca
    aca <-->|Entra ID, no API key| aoai
    aca -->|telemetry| obs
    acr -->|pull image| aca
```

## Key choices

- **One Container App, one agent.** No separate frontend service, no MCP server, no Postgres.
- **Two model tiers.** `gpt-5.4-mini` runs the support driver; the much cheaper `gpt-5-nano` runs the three reliability middlewares.
- **In-memory data.** Knowledge-base lookups are NumPy cosine similarity over pre-computed embeddings; everything else is dictionary access into JSON loaded at startup.
- **Entra ID, no API keys.** The Container App's managed identity is assigned the Cognitive Services User role on Azure OpenAI; tokens come from `DefaultAzureCredential`.
- **Streaming.** The Responses API streams `output_text` deltas; Starlette forwards them as Server-Sent Events to the browser.

## Layered explainers

- [Layer 1 — Primary agent + 4 middlewares](slides/layer-1-middlewares.md)
- [Layer 2 — Handoffs via `apply_step_config`](slides/layer-2-handoffs.md)
