"""pgvector embeddings store — pre-built for Phase 2 RAG.

Each row links a source document (transaction description, chat message,
financial doc) to its embedding vector. The HNSW index on the vector column
enables sub-millisecond ANN search across millions of rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # What kind of content: 'transaction' | 'chat_message' | 'document'
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # The text that was embedded (for re-ranking / display)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Vector stored as TEXT (real pgvector type added via raw DDL in migration).
    # The column is defined there as vector(1536) for text-embedding-3-small.
    # We keep a JSONB shadow here so SQLAlchemy can import without pgvector lib.
    vector_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    model: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="text-embedding-3-small"
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Embedding {self.source_type}/{self.source_id}>"
