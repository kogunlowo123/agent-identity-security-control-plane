"""LangGraph state definition for agent orchestration."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class RetrievedChunk(TypedDict):
    chunk_id: str
    content: str
    document_source: str
    score: float
    metadata: dict[str, Any]


class IdentityRecord(TypedDict):
    id: str
    name: str
    spiffe_id: str
    tier: str
    status: str
    capabilities: list[str]


class AgentState(TypedDict):
    """Typed state for LangGraph identity audit agent."""

    # Conversation history (append-only via add_messages reducer)
    messages: Annotated[list[BaseMessage], add_messages]

    # RAG retrieval results
    retrieved_chunks: list[RetrievedChunk]

    # Query context
    query: str
    identity_id: str | None
    identity_record: IdentityRecord | None

    # Agent metadata
    agent_id: str
    session_id: str
    tier: str

    # Orchestration control
    retrieval_quality_score: float  # 0.0 - 1.0
    grounding_score: float  # 0.0 - 1.0
    decision: str | None  # "allow" | "deny" | "review"
    requires_human_review: bool

    # Output
    final_report: str | None
    citations: list[str]

    # Error tracking
    error: str | None
    retry_count: int
