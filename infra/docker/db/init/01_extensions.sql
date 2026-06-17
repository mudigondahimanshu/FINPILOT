-- FinPilot DB bootstrap: enable required extensions.
-- Runs once on first container start (docker-entrypoint-initdb.d).

-- Time-series hypertables for transactions + OHLC market data.
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Vector similarity search for the RAG copilot (pgvector).
CREATE EXTENSION IF NOT EXISTS vector;

-- Field-level encryption / hashing helpers for PII.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- UUID generation.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
