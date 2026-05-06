"""Build the LangChain v1 customer-support agent.

`build_agent` is called once from the Starlette lifespan. It assembles:
  - A main `ChatOpenAI(use_responses_api=True)` model for the support driver.
  - A cheap `gpt-5-nano` model for refine + validate + summarisation.
  - All tools from `app.tools.ALL_TOOLS`.
  - Middleware: refine_query, apply_step_config (handoffs), validate_response,
    SummarizationMiddleware.
  - InMemorySaver checkpointer.
"""

from __future__ import annotations

import logging
import os

from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from app.data_loader import AppData
from app.middleware import apply_step_config
from app.middleware.refine import make_refine_query
from app.middleware.validate import make_validate_response
from app.state import SupportState
from app.tools import ALL_TOOLS

logger = logging.getLogger(__name__)


def _aoai_v1_endpoint() -> str:
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    if not endpoint.endswith("/openai/v1"):
        endpoint = f"{endpoint}/openai/v1"
    return endpoint


def build_models() -> tuple[ChatOpenAI, ChatOpenAI, DefaultAzureCredential]:
    """Create the main (gpt-5.4-mini drives the main agent) + nano models (used for middleware tasks)."""
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    base_url = _aoai_v1_endpoint()

    main = ChatOpenAI(
        model=os.getenv("AZURE_OPENAI_MAIN_DEPLOYMENT", "gpt-5.4-mini"),
        base_url=base_url,
        api_key=token_provider,
        streaming=True,
        use_responses_api=True,
    )
    nano = ChatOpenAI(
        model=os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT", "gpt-5-nano"),
        base_url=base_url,
        api_key=token_provider,
        streaming=False,
        use_responses_api=True,
        # Tag every nano call so the chat UI can filter its tokens out of
        # the visible bubble (refine/validate output is internal-only).
        tags=["nano-utility"],
    )
    return main, nano, credential


def build_agent(main_model: ChatOpenAI, nano_model: ChatOpenAI):
    """Compile the customer-support agent."""

    # makes user queries more explicit
    refine_query = make_refine_query(nano_model)
    # checks agent response is grounded in data
    validate_response = make_validate_response(nano_model)
    #summarises conversation when it exceeds token limit to preserve context while keeping within model limits
    summariser = SummarizationMiddleware(model=nano_model, max_tokens_before_summary=4000)

    return create_agent(
        model=main_model,
        tools=ALL_TOOLS,
        state_schema=SupportState,
        middleware=[
            refine_query,
            apply_step_config,
            validate_response,
            summariser,
        ],
        checkpointer=InMemorySaver(),
    )


__all__ = ["build_agent", "build_models", "AppData"]
