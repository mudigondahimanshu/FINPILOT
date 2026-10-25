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
_MIN_RELEVANCE = 0.45
_MAX_CHUNK = 512  # characters
_LLM_TIMEOUT = 30.0  # seconds

_SYSTEM_PROMPT = (
    "You are FinPilot, a personalized AI financial copilot. You are given (a) retrieved "
    "knowledge-base context and, only when relevant, (b) a small part of the user's own "
    "financial profile. Answer the question asked first. Never repeat or dump the full "
    "financial profile. Use only profile facts that directly help answer this question. "
    "Do not force personalization into unrelated questions or small talk. Treat old assistant "
    "messages in conversation history as context only; use them to resolve follow-up references, "
    "and do not repeat an old answer unless asked. "
    "Cite knowledge-base "
    "sources as [1], [2], etc. "
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
    relevant_chunks = [chunk for chunk in chunks if chunk.get("similarity", 0) >= _MIN_RELEVANCE][:3]
    context = "\n\n".join(
        f"[{i+1}] {chunk['content']}" for i, chunk in enumerate(relevant_chunks)
    )
    sources = [{"id": str(i + 1), **chunk} for i, chunk in enumerate(relevant_chunks)]

    relevant_user_context = _relevant_user_context(question, user_context)
    personalized = bool(relevant_user_context)

    # Build reasoning: explain which sources informed the answer
    reason_parts: list[str] = []
    if relevant_chunks:
        top_sim = relevant_chunks[0]["similarity"]
        reason_parts.append(
            f"Found {len(relevant_chunks)} relevant document chunk(s) with top similarity {top_sim:.2f}, "
            f"grounded in: {', '.join(f'[{i+1}]' for i in range(len(relevant_chunks)))}."
        )
    else:
        reason_parts.append("No matching knowledge-base documents for this query.")
    if personalized:
        reason_parts.append("Relevant account information was used to answer this question.")
    reasoning = " ".join(reason_parts)

    generated = await asyncio.to_thread(
        _generate, question, context, history or [], relevant_user_context
    )
    if generated is not None:
        answer_text, model = generated
    else:
        answer_text, model = _local_answer(question, relevant_chunks, relevant_user_context), "local"

    return {
        "answer": answer_text, "sources": sources,
        "reasoning": reasoning, "model": model,
        "personalized": personalized,
    }


# ── LLM provider chain ────────────────────────────────────────────────────────

def _build_messages(
    question: str, context: str, history: list[dict], user_context: str | None
) -> list[dict]:
    user_block = (
        "Retrieved reference material (use only if it helps answer the question):\n"
        f"{context or '(no relevant reference material found)'}\n\n"
    )
    if user_context:
        user_block += (
            "Relevant user financial facts (use only the facts that directly help; "
            "never repeat this block verbatim):\n"
            f"{user_context}\n\n"
        )
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
    normalized = " ".join(question.lower().strip().split())

    # Useful, deterministic answers for common prompts when no language model
    # provider is configured. These templates answer the question directly and
    # avoid pretending the user's spending history contains tax or coding data.
    if any(token in normalized for token in ("haha", "lol", "😂", "😄")) and len(normalized) < 40:
        return "🙂 What would you like to explore next?"
    if normalized in {"hi", "hello", "hey", "thanks", "thank you", "thank you!"}:
        return "Hi! Ask me about budgeting, spending, subscriptions, goals, or a general finance concept."
    if any(token in normalized for token in ("python", "pythin", "pyhton", "pyton")) and any(
        token in normalized for token in ("print", "output", "display")
    ):
        return (
            "Use Python's `print()` function to show text or a value:\n\n"
            "```python\n"
            'print("Hello, world!")\n'
            "\n"
            "amount = 250\n"
            "print(amount)\n"
            "```"
        )
    if "capital gain" in normalized or "capital gains" in normalized:
        return (
            "A basic capital-gain calculation is:\n\n"
            "**Capital gain = sale proceeds − eligible purchase cost − eligible selling costs.**\n\n"
            "Then determine which part is taxable after any applicable exemptions or loss set-offs, "
            "and apply the rate and rules for the asset and tax year. In India, the treatment can "
            "vary by asset type, purchase and sale dates, holding period, and the tax rules in force. "
            "Your FinPilot profile does not include asset purchase prices or sale details, so it "
            "cannot calculate your personal tax bill from the current data.\n\n"
            "To estimate it, gather the asset type, purchase date and cost, sale date and proceeds, "
            "eligible fees, and any capital losses or exemptions. Verify current rates with the "
            "Income Tax Department or a qualified tax professional."
        )

    relevant_context = user_context or ""
    relevant_chunks = [c for c in chunks if c.get("similarity", 0) >= _MIN_RELEVANCE][:3]
    if relevant_chunks:
        snippets = "\n\n".join(
            f"[{index}] {chunk['content'][:500].strip()}"
            for index, chunk in enumerate(relevant_chunks, start=1)
        )
        return f"I found these reference notes that may help answer your question:\n\n{snippets}"
    if relevant_context:
        # This is only reached for a question that explicitly asks about the
        # user's own finances. Share the relevant subsection, not the full profile.
        return f"From the information available in your account:\n\n{relevant_context}"
    return (
        "I don't have a configured language model or a matching reference document to answer "
        "that question yet. I can still help with common topics such as capital-gains basics, "
        "Python `print()` examples, and questions about the data available in your FinPilot account."
    )


def _relevant_user_context(question: str, user_context: str | None) -> str:
    """Select only profile lines that match an explicitly personal finance question."""
    if not user_context:
        return ""
    q = question.lower()
    words = set(q.replace("?", " ").replace("!", " ").replace(",", " ").split())
    personal_question = bool(words & {"my", "mine", "our", "ours"}) or any(
        phrase in q for phrase in ("for me", "in my account", "how am i doing")
    )
    if not personal_question:
        return ""
    categories: list[str] = []
    if any(word in q for word in ("spend", "spending", "expense", "income", "cash flow", "saving rate", "how am i doing")):
        categories.extend(("Income", "Expenses", "Savings rate", "Top spending categories"))
    if any(word in q for word in ("budget", "budgets", "limit")):
        categories.append("Active budgets")
    if any(word in q for word in ("goal", "goals", "allocate", "saved")):
        categories.append("Savings goals")
    if any(word in q for word in ("subscription", "subscriptions", "recurring payment")):
        categories.append("Recurring payments")
    if any(word in q for word in ("risk profile", "risk tolerance")):
        categories.append("Inferred risk profile")
    if not categories:
        return ""
    lines = [
        line.strip()
        for line in user_context.splitlines()
        if any(category.lower() in line.lower() for category in categories)
    ]
    return "\n".join(lines)
