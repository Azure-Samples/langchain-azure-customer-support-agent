"""Help-center semantic search using NumPy cosine over pre-computed embeddings."""

from __future__ import annotations

from typing import Annotated

import numpy as np
from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.data_loader import get_app_data
from app.state import SupportState
from app.tools.catalog import _embed


@tool
async def search_help_center(
    query: str,
    runtime: ToolRuntime[None, SupportState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    k: int = 4,
) -> Command:
    """Search Zava's help-center articles by semantic similarity. Returns article excerpts with [doc_id] tags."""
    data = get_app_data()
    if data is None or not data.kb_articles:
        return Command(
            update={"messages": [ToolMessage("Help center not loaded.", tool_call_id=tool_call_id)]}
        )

    qv = await _embed(query)
    matrix = data.kb_embeddings
    if matrix.shape[0] == 0:
        return Command(
            update={"messages": [ToolMessage("No help-center embeddings available.", tool_call_id=tool_call_id)]}
        )
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
    qv_norm = qv / (np.linalg.norm(qv) + 1e-9)
    sims = matrix_norm @ qv_norm
    top_idx = np.argsort(-sims)[:k]

    retrieved_ids: list[str] = []
    lines: list[str] = []
    for i in top_idx:
        article = data.kb_articles[int(i)]
        doc_id = article.get("article_id") or article.get("id") or f"kb-{i}"
        retrieved_ids.append(str(doc_id))
        title = article.get("title", "(untitled)")
        excerpt = (article.get("content", "") or "")[:400]
        lines.append(f"[{doc_id}] {title}\n{excerpt}")

    return Command(
        update={
            "last_retrieved_docs": retrieved_ids,
            "messages": [ToolMessage("\n\n".join(lines), tool_call_id=tool_call_id)],
        }
    )
