# mypy: disable-error-code="arg-type,union-attr"
"""RAG Copilot (Phase 3.5).

Pipeline:
  1. Ingest  — chunk text (financial PDFs / regulations) → sentence-transformer
               embeddings (384-dim, all-MiniLM-L6-v2) → upsert into pgvector.
  2. Retrieve — embed user query → cosine ANN search (top-5 chunks).
  3. Generate — pass retrieved context + conversation history to Claude Haiku;
               return grounded answer + source citations.

Embedding model: sentence-transformers/all-MiniLM-L6-v2 (90 MB, local, no API key).
LLM: claude-haiku-4-5-20251001 via Anthropic API (ANTHROPIC_API_KEY env var required).
     Falls back to a template answer when API key is not set.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_EMBED_MODEL = "all-MiniLM-L6-v2"
_EMBED_DIM = 384
_TOP_K = 5
_MAX_CHUNK = 512  # characters

_embedder: object | None = None


# ── Embedding ─────────────────────────────────────────────────────────────────

def _get_embedder() -> object:
    global _embedder  # noqa: PLW0603
    if _embedder is None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        _embedder = SentenceTransformer(_EMBED_MODEL)
    return _embedder


def _embed(texts: list[str]) -> list[list[float]]:
    model = _get_embedder()
    vecs = model.encode(texts, normalize_embeddings=True)  # type: ignore[attr-defined]
    return [v.tolist() for v in vecs]


# ── Ingestion ─────────────────────────────────────────────────────────────────

async def ingest_document(session: AsyncSession, title: str, body: str) -> int:
    """Chunk *body* into ≤512-char segments, embed, store in pgvector embeddings table."""
    chunks = _chunk_text(body, _MAX_CHUNK)
    if not chunks:
        return 0

    vecs = await asyncio.to_thread(_embed, chunks)

    from sqlalchemy import text  # noqa: PLC0415
    inserted = 0
    for chunk, vec in zip(chunks, vecs, strict=False):
        await session.execute(
            text(
                """
                INSERT INTO embeddings (id, content, metadata, embedding)
                VALUES (:id, :content, :meta, :vec::vector)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "content": chunk,
                "meta": json.dumps({"title": title}),
                "vec": _vec_to_pg(vec),
            },
        )
        inserted += 1
    await session.commit()
    return inserted


def _chunk_text(text: str, max_len: int) -> list[str]:
    sentences = text.replace("\n", " ").split(". ")
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 2 <= max_len:
            current += sent + ". "
        else:
            if current.strip():
                chunks.append(current.strip())
            current = sent + ". "
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _vec_to_pg(vec: list[float]) -> str:
    """Format as PostgreSQL vector literal '[0.1, 0.2, ...]'."""
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


# ── Retrieval ─────────────────────────────────────────────────────────────────

async def retrieve(session: AsyncSession, query: str, k: int = _TOP_K) -> list[dict]:
    """Return top-k chunks most similar to *query* via pgvector cosine search."""
    vec = await asyncio.to_thread(_embed, [query])
    q_vec = _vec_to_pg(vec[0])

    from sqlalchemy import text  # noqa: PLC0415
    result = await session.execute(
        text(
            f"""
            SELECT id, content, metadata,
                   1 - (embedding <=> '{q_vec}'::vector) AS similarity
            FROM embeddings
            ORDER BY embedding <=> '{q_vec}'::vector
            LIMIT {k}
            """  # noqa: S608
        )
    )
    return [
        {"id": str(r.id), "content": r.content, "metadata": r.metadata, "similarity": float(r.similarity)} # noqa: E501
        for r in result.fetchall()
    ]


# ── Generation ────────────────────────────────────────────────────────────────

async def answer(
    session: AsyncSession,
    question: str,
    history: list[dict] | None = None,
) -> dict:
    """Retrieve relevant chunks then generate a grounded answer."""
    chunks = await retrieve(session, question)
    context = "\n\n".join(f"[{i+1}] {c['content']}" for i, c in enumerate(chunks))
    sources = [{"id": str(i + 1), **c} for i, c in enumerate(chunks)]

    # Build reasoning: explain which sources informed the answer
    if chunks:
        top_sim = chunks[0]["similarity"]
        reasoning = (
            f"Found {len(chunks)} relevant document chunk(s) with top similarity {top_sim:.2f}. "
            f"Answer grounded in: {', '.join(f'[{i+1}]' for i in range(len(chunks)))}."
        )
    else:
        reasoning = "No relevant documents found in the knowledge base for this query."

    if not _ANTHROPIC_KEY:
        return {
            "answer": _template_answer(question, chunks),
            "sources": sources,
            "reasoning": reasoning,
            "model": "template",
        }

    answer_text = await asyncio.to_thread(
        _claude_generate, question, context, history or []
    )
    return {
        "answer": answer_text, "sources": sources,
        "reasoning": reasoning, "model": "claude-haiku",
    }


def _claude_generate(question: str, context: str, history: list[dict]) -> str:
    import anthropic  # noqa: PLC0415

    client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
    system = (
        "You are FinPilot, an AI financial copilot. Answer questions using ONLY the provided "
        "context. Cite sources as [1], [2], etc. If the context doesn't contain the answer, "
        "say so. Never give personalised investment advice."
    )
    messages = [
        *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def _template_answer(question: str, chunks: list[dict]) -> str:
    if not chunks:
        return "I don't have relevant information to answer that question."
    top = chunks[0]["content"][:300]
    return (
        f"Based on available documentation: {top}...\n\n"
        "(Set ANTHROPIC_API_KEY for full AI-powered answers.)"
    )
