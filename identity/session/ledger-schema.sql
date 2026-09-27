-- Agent Identity Security Control Plane - Session Ledger Schema
-- PostgreSQL 16+ with pgvector extension

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pgvector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- Agent Identity Registry
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_identities (
    id                  VARCHAR(64) PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    spiffe_id           VARCHAR(512) UNIQUE NOT NULL,
    tier                VARCHAR(2) NOT NULL CHECK (tier IN ('T0', 'T1', 'T2', 'T3')),
    status              VARCHAR(16) NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'suspended', 'revoked', 'pending')),
    capabilities        TEXT[] NOT NULL DEFAULT '{}',
    authorized_tools    TEXT[] NOT NULL DEFAULT '{}',
    max_delegation_depth SMALLINT NOT NULL DEFAULT 0 CHECK (max_delegation_depth BETWEEN 0 AND 5),
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at          TIMESTAMPTZ,
    revocation_reason   TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_identities_spiffe_id
    ON agent_identities(spiffe_id);
CREATE INDEX IF NOT EXISTS idx_agent_identities_tier_status
    ON agent_identities(tier, status);

-- ---------------------------------------------------------------------------
-- Sessions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sessions (
    session_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id            VARCHAR(64) NOT NULL REFERENCES agent_identities(id),
    principal_spiffe_id VARCHAR(512) NOT NULL,
    tier                VARCHAR(2) NOT NULL,
    status              VARCHAR(16) NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'completed', 'failed', 'expired')),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}',
    token_jti           UUID,
    client_ip           INET,
    user_agent          VARCHAR(512)
);

CREATE INDEX IF NOT EXISTS idx_sessions_agent_id
    ON sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at
    ON sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status
    ON sessions(status);

-- ---------------------------------------------------------------------------
-- Identity Events (audit log)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS identity_events (
    event_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type          VARCHAR(64) NOT NULL,
    -- e.g. identity.issued, identity.revoked, identity.violated, identity.validated
    agent_id            VARCHAR(64),
    session_id          UUID REFERENCES sessions(session_id),
    principal_spiffe_id VARCHAR(512),
    tier                VARCHAR(2),
    token_jti           UUID,
    outcome             VARCHAR(16) NOT NULL CHECK (outcome IN ('allowed', 'denied', 'error')),
    policy_decision     JSONB,
    metadata            JSONB NOT NULL DEFAULT '{}',
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_ip           INET,
    trace_id            VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_identity_events_agent_id
    ON identity_events(agent_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_identity_events_type
    ON identity_events(event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_identity_events_occurred_at
    ON identity_events(occurred_at DESC);

-- ---------------------------------------------------------------------------
-- Delegation Chains
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS delegation_chains (
    chain_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    delegator_spiffe_id VARCHAR(512) NOT NULL,
    delegate_spiffe_id  VARCHAR(512) NOT NULL,
    delegator_tier      VARCHAR(2) NOT NULL,
    delegate_tier       VARCHAR(2) NOT NULL,
    capabilities        TEXT[] NOT NULL,
    depth               SMALLINT NOT NULL DEFAULT 1,
    not_before          TIMESTAMPTZ NOT NULL,
    not_after           TIMESTAMPTZ NOT NULL,
    signature           TEXT NOT NULL,
    parent_chain_id     UUID REFERENCES delegation_chains(chain_id),
    revoked             BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_delegation_chains_delegator
    ON delegation_chains(delegator_spiffe_id, not_after);
CREATE INDEX IF NOT EXISTS idx_delegation_chains_delegate
    ON delegation_chains(delegate_spiffe_id, not_after);

-- ---------------------------------------------------------------------------
-- Token Revocation List
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS token_revocations (
    jti                 UUID PRIMARY KEY,
    agent_id            VARCHAR(64),
    principal_spiffe_id VARCHAR(512),
    tier                VARCHAR(2),
    revoked_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ NOT NULL,
    -- Keep entries until token would have naturally expired
    reason              TEXT,
    revoked_by          VARCHAR(512)
);

CREATE INDEX IF NOT EXISTS idx_token_revocations_expires_at
    ON token_revocations(expires_at);

-- ---------------------------------------------------------------------------
-- RAG Chunks (for pgvector retrieval)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id         VARCHAR(256) NOT NULL,
    document_source     VARCHAR(512) NOT NULL,
    content             TEXT NOT NULL,
    content_hash        VARCHAR(64) NOT NULL,
    embedding           vector(1024),
    -- BAAI/bge-large-en-v1.5 dimension
    chunk_index         INTEGER NOT NULL,
    total_chunks        INTEGER NOT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}',
    acl_labels          TEXT[] NOT NULL DEFAULT '{}',
    has_pii             BOOLEAN NOT NULL DEFAULT FALSE,
    topics              TEXT[] NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_document_id
    ON rag_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding
    ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_topics
    ON rag_chunks USING gin(topics);

-- ---------------------------------------------------------------------------
-- Automatic updated_at trigger
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_agent_identities_updated_at
    BEFORE UPDATE ON agent_identities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ---------------------------------------------------------------------------
-- Cleanup job: remove expired revocations
-- ---------------------------------------------------------------------------

-- Run periodically via pg_cron or application scheduler
-- DELETE FROM token_revocations WHERE expires_at < now();
