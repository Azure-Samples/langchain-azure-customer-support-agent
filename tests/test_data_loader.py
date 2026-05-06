"""Smoke test that data_loader can load committed JSON without AOAI access.

Skips embeddings recomputation by ensuring kb_embeddings.npy exists (or that
AZURE_OPENAI_ENDPOINT is unset, in which case load_all will skip and the
NumPy array will simply be empty).
"""

import asyncio
import os
from pathlib import Path

import pytest

from app.data_loader import DATA_DIR, load_all


@pytest.mark.skipif(not (DATA_DIR / "customers.json").exists(), reason="run generate_sample_data.py first")
def test_data_loader_loads_static_files(monkeypatch):
    # Force-skip embedding compute by clearing env.
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

    # Pre-place a stub kb_embeddings.npy so load_all doesn't need AOAI.
    npy = DATA_DIR / "kb_embeddings.npy"
    created = False
    if not npy.exists():
        import numpy as np
        articles_count = len(__import__("json").loads((DATA_DIR / "kb_articles.json").read_text()))
        np.save(npy, __import__("numpy").zeros((articles_count, 1536), dtype="float32"))
        created = True
    try:
        data = asyncio.run(load_all())
        assert len(data.customers) > 0
        assert len(data.orders) > 0
        assert len(data.products) > 0
        assert data.kb_embeddings.shape[0] == len(data.kb_articles)
    finally:
        if created:
            npy.unlink(missing_ok=True)
