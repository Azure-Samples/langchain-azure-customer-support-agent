"""Catalog tools: semantic product search + warranty lookup.

Product semantic search uses pre-computed `description_embedding` fields on
each product. Query embedding is computed live via the AOAI embedding
deployment.
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
from langchain.tools import ToolRuntime, tool

from app.data_loader import get_app_data
from app.state import SupportState


def _data(runtime: ToolRuntime):
    return get_app_data()


@lru_cache(maxsize=1)
def _embed_client():
    from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
    from openai import AsyncAzureOpenAI

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    return AsyncAzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/"),
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )


async def _embed(text: str) -> np.ndarray:
    client = _embed_client()
    deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    resp = await client.embeddings.create(model=deployment, input=text)
    return np.array(resp.data[0].embedding, dtype=np.float32)


@tool
async def semantic_search_products(
    query: str,
    runtime: ToolRuntime[None, SupportState],
    k: int = 5,
) -> str:
    """Search Zava's product catalog by natural-language description."""
    data = _data(runtime)
    if not data or not data.products:
        return "Catalog not loaded."

    products_with_emb = [p for p in data.products if isinstance(p.get("description_embedding"), list)]
    if not products_with_emb:
        # Fallback to substring match
        q = query.lower()
        hits = [p for p in data.products if q in p.get("product_description", "").lower()
                or q in p.get("product_name", "").lower()][:k]
        if not hits:
            return f"No products found matching '{query}'."
        return "\n".join(
            f"- [{p['sku']}] {p['product_name']} — ${p.get('base_price', 0):.2f}: {p.get('product_description', '')[:120]}"
            for p in hits
        )

    qv = await _embed(query)
    matrix = np.array([p["description_embedding"] for p in products_with_emb], dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9
    qv /= np.linalg.norm(qv) + 1e-9
    sims = matrix @ qv
    top_idx = np.argsort(-sims)[:k]
    lines = []
    for i in top_idx:
        p = products_with_emb[i]
        lines.append(
            f"- [{p['sku']}] {p['product_name']} — ${p.get('base_price', 0):.2f} "
            f"(score={float(sims[i]):.2f}): {p.get('product_description', '')[:120]}"
        )
    return "\n".join(lines)


@tool
def check_warranty(sku: str, runtime: ToolRuntime[None, SupportState]) -> str:
    """Return the warranty terms for a SKU based on its category."""
    data = _data(runtime)
    if not data:
        return "Catalog not loaded."
    product = data.products_by_sku.get(sku)
    if not product:
        return f"SKU {sku} not found."
    category = product.get("category_name", "").lower()
    terms = data.warranty_by_category.get(category)
    if not terms:
        return f"No warranty terms recorded for category '{product.get('category_name')}'."
    return (
        f"{product['product_name']} (SKU {sku}) — Category: {product.get('category_name')}. "
        f"Warranty: {terms.get('warranty_months')} months. "
        f"Covered: {', '.join(terms.get('covered_defects', [])) or 'manufacturing defects'}. "
        f"Excluded: {', '.join(terms.get('exclusions', [])) or 'normal wear and tear'}."
    )
