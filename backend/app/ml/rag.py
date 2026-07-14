# mypy: disable-error-code="arg-type,union-attr"
"""RAG Copilot (Phase 3.5).

Pipeline:
  1. Ingest  — chunk text (financial PDFs / regulations) → sentence-transformer
               embeddings (384-dim, all-MiniLM-L6-v2) → upsert into pgvector.
  2. Retrieve — embed user query → cosine ANN search (top-5 chunks).
  3. Generate — pass retrieved context + conversation history to an LLM;
               return grounded answer + source citations.

Embedding model: sentence-transformers/all-MiniLM-L6-v2 (90 MB, local, no API key).

Generation is provider-agnostic. End users never supply a key — the copilot
always answers. The operator MAY set one server-side env var to upgrade answer
quality; providers are tried in order and the first configured one wins:

  1. GROQ_API_KEY       — Groq free tier (Llama 3.3 70B, fast)
  2. GEMINI_API_KEY     — Google AI Studio free tier (Gemini Flash)
  3. ANTHROPIC_API_KEY  — Claude Haiku
  4. OLLAMA_URL         — self-hosted local model (e.g. http://localhost:11434)
  5. (none)             — built-in keyless answer engine over the retrieved
                          chunks + the user's own financial snapshot
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

_EMBED_MODEL = "all-MiniLM-L6-v2"
_EMBED_DIM = 384
_TOP_K = 5
_MAX_CHUNK = 512  # characters
_LLM_TIMEOUT = 30.0  # seconds

_SYSTEM_PROMPT = (
    "You are FinPilot, a personalized AI financial copilot. You are given (a) retrieved "
    "knowledge-base context and (b) the user's own financial profile. Tailor your answer "
    "to the user's actual spending, budgets, risk profile, and portfolio when relevant, "
    "and reference their real numbers. Cite knowledge-base sources as [1], [2], etc. "
    "Give educational, data-grounded guidance — explain trade-offs and general principles "
    "rather than issuing licensed investment advice, and remind the user to do their own "
    "research for specific buy/sell decisions. If you lack the data to answer, say so."
)

_embedder: object | None = None


# ── Embedding ─────────────────────────────────────────────────────────────────

def _get_embedder() -> object:
    global _embedder  # noqa: PLW0603
    if os.getenv("DISABLE_EMBEDDINGS", "") == "1":
        msg = "embeddings disabled via DISABLE_EMBEDDINGS=1"
        raise RuntimeError(msg)
    if _embedder is None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        _embedder = SentenceTransformer(_EMBED_MODEL)
    return _embedder


def preload_embedder() -> None:
    """Warm the embedding model so the first copilot question isn't slow.

    Called from app startup in a background thread; failures are logged and
    ignored — the copilot degrades gracefully without retrieval.
    """
    try:
        _get_embedder()
        log.info("embedding model %s preloaded", _EMBED_MODEL)
    except Exception as exc:
        log.warning("embedding model unavailable (%s); copilot runs without RAG", exc)


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
                VALUES (:id, :content, :meta, CAST(:vec AS vector))
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
            """
            SELECT id, content, metadata,
                   1 - (embedding <=> CAST(:q_vec AS vector)) AS similarity
            FROM embeddings
            ORDER BY embedding <=> CAST(:q_vec AS vector)
            LIMIT :k
            """
        ),
        {"q_vec": q_vec, "k": k},
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
    user_context: str | None = None,
) -> dict:
    """Retrieve relevant chunks then generate a grounded, personalized answer.

    *user_context* is an optional natural-language snapshot of the signed-in
    user's finances (spending, budgets, goals, subscriptions). When provided,
    the copilot tailors its answer to the user's actual data.

    Retrieval is best-effort: on hosts without the embedding model (e.g.
    low-memory free tiers with DISABLE_EMBEDDINGS=1) the copilot still answers
    from the user's own financial context.
    """
    try:
        chunks = await retrieve(session, question)
    except Exception as exc:
        log.warning("retrieval unavailable, answering without knowledge base: %s", exc)
        chunks = []
    context = "\n\n".join(f"[{i+1}] {c['content']}" for i, c in enumerate(chunks))
    sources = [{"id": str(i + 1), **c} for i, c in enumerate(chunks)]

    personalized = bool(user_context)

    # Build reasoning: explain which sources informed the answer
    reason_parts: list[str] = []
    if chunks:
        top_sim = chunks[0]["similarity"]
        reason_parts.append(
            f"Found {len(chunks)} relevant document chunk(s) with top similarity {top_sim:.2f}, "
            f"grounded in: {', '.join(f'[{i+1}]' for i in range(len(chunks)))}."
        )
    else:
        reason_parts.append("No matching knowledge-base documents for this query.")
    if personalized:
        reason_parts.append("Answer personalized using your spending, budgets, and portfolio.")
    reasoning = " ".join(reason_parts)

    generated = await asyncio.to_thread(
        _generate, question, context, history or [], user_context
    )
    if generated is not None:
        answer_text, model = generated
    else:
        answer_text, model = _local_answer(question, chunks, user_context), "local"

    return {
        "answer": answer_text, "sources": sources,
        "reasoning": reasoning, "model": model,
        "personalized": personalized,
    }


# ── LLM provider chain ────────────────────────────────────────────────────────

def _build_messages(
    question: str, context: str, history: list[dict], user_context: str | None
) -> list[dict]:
    user_block = f"Context:\n{context}\n\n"
    if user_context:
        user_block += f"{user_context}\n\n"
    user_block += f"Question: {question}"
    return [
        *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
        {"role": "user", "content": user_block},
    ]


def _generate(
    question: str,
    context: str,
    history: list[dict],
    user_context: str | None = None,
) -> tuple[str, str] | None:
    """Try each configured provider in order; return (answer, model) or None."""
    from app.core.config import settings  # noqa: PLC0415

    messages = _build_messages(question, context, history, user_context)
    providers = [
        (settings.groq_api_key, _groq_generate),
        (settings.gemini_api_key, _gemini_generate),
        (settings.anthropic_api_key, _anthropic_generate),
        (settings.ollama_url, _ollama_generate),
    ]
    for credential, generate in providers:
        if not credential:
            continue
        try:
            return generate(credential, messages)
        except Exception as exc:
            log.warning("%s failed, trying next provider: %s", generate.__name__, exc)
    return None


def _groq_generate(api_key: str, messages: list[dict]) -> tuple[str, str]:
    """Groq free tier — OpenAI-compatible chat completions."""
    import httpx  # noqa: PLC0415

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "max_tokens": 512,
            "messages": [{"role": "system", "content": _SYSTEM_PROMPT}, *messages],
        },
        timeout=_LLM_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"], f"groq/{model}"


def _gemini_generate(api_key: str, messages: list[dict]) -> tuple[str, str]:
    """Google AI Studio free tier."""
    import httpx  # noqa: PLC0415

    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": api_key},
        json={
            "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 512},
        },
        timeout=_LLM_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    return text, f"gemini/{model}"


def _anthropic_generate(api_key: str, messages: list[dict]) -> tuple[str, str]:
    import anthropic  # noqa: PLC0415

    client = anthropic.Anthropic(api_key=api_key)
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text, f"anthropic/{model}"


def _ollama_generate(base_url: str, messages: list[dict]) -> tuple[str, str]:
    """Self-hosted Ollama — free, local, no key."""
    import httpx  # noqa: PLC0415

    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    resp = httpx.post(
        f"{base_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": _SYSTEM_PROMPT}, *messages],
        },
        timeout=max(_LLM_TIMEOUT, 120.0),  # local inference can be slow
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"], f"ollama/{model}"


# ── Keyless answer engine (always available) ─────────────────────────────────

def _local_answer(
    question: str, chunks: list[dict], user_context: str | None = None
) -> str:
    """Compose a grounded answer from retrieved chunks + the user's own data.

    No external API involved, so the copilot always responds even with zero
    provider configuration.
    """
    parts: list[str] = []

    relevant = [c for c in chunks if c.get("similarity", 0) > 0.3][:3]
    if relevant:
        parts.append("Here's what the knowledge base says about your question:")
        for i, chunk in enumerate(relevant, start=1):
            excerpt = chunk["content"][:400].strip()
            parts.append(f"[{i}] {excerpt}")
    if user_context:
        parts.append(
            "Looking at your own finances, here's the snapshot I'd weigh this against:\n"
            + user_context
        )
    if not relevant and not user_context:
        return (
            "I couldn't find knowledge-base material matching that question, and I "
            "don't have enough of your financial data yet to answer from it. Try "
            "importing your transactions or asking about budgeting, investing "
            "basics, or your spending."
        )
    parts.append(
        "This summary is drawn directly from your data and the cited sources — "
        "consider it a starting point and do your own research before acting on it."
    )
    return "\n\n".join(parts)
