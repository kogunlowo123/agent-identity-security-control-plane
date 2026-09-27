"""
LangGraph identity audit agent graph.

Nodes:
  retrieve_context → analyze_identity → generate_report → cite_sources

Conditional edges:
  - After retrieve_context: if quality score < threshold, retry or fallback
  - After generate_report: grounding check before final output
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from litellm import completion

from .state import AgentState, RetrievedChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RETRIEVAL_QUALITY_THRESHOLD = 0.5
GROUNDING_THRESHOLD = 0.7
MAX_RETRIES = 2

SYSTEM_PROMPT = """You are an expert AI identity security auditor specializing in:
- SPIFFE/SPIRE identity infrastructure
- JWT token lifecycle management and security
- NIST SP 800-207 Zero Trust Architecture
- OAuth 2.0 and related identity RFCs

Your role is to analyze agent identity records and generate factual audit reports
grounded in retrieved context. Every claim must be supported by a citation.

When analyzing identity records, focus on:
1. SPIFFE ID validity and trust domain alignment
2. Tier appropriateness for the agent's stated capabilities
3. Delegation depth limits compliance
4. Token TTL configuration
5. Capability scope correctness
"""


# ---------------------------------------------------------------------------
# Node: retrieve_context
# ---------------------------------------------------------------------------

async def retrieve_context(state: AgentState) -> dict[str, Any]:
    """Retrieve relevant context from RAG core for the identity audit query."""
    rag_core_url = os.getenv("RAG_CORE_URL", "http://localhost:8200")
    query = state.get("query", "")
    identity_id = state.get("identity_id", "")

    # Construct enriched query
    search_query = f"identity audit {identity_id}: {query}" if identity_id else query

    retrieved: list[RetrievedChunk] = []
    quality_score = 0.0

    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{rag_core_url}/retrieve",
                json={
                    "query": search_query,
                    "top_k": 10,
                    "use_hybrid": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            chunks = data.get("chunks", [])
            retrieved = [
                RetrievedChunk(
                    chunk_id=c.get("chunk_id", ""),
                    content=c.get("content", ""),
                    document_source=c.get("document_source", ""),
                    score=float(c.get("score", 0.0)),
                    metadata=c.get("metadata", {}),
                )
                for c in chunks
            ]
            # Quality score = mean of top-3 chunk scores
            top_scores = sorted([c["score"] for c in retrieved], reverse=True)[:3]
            quality_score = sum(top_scores) / max(len(top_scores), 1)

    except Exception as exc:
        logger.warning("RAG retrieval failed: %s — proceeding without context", exc)
        quality_score = 0.0

    return {
        "retrieved_chunks": retrieved,
        "retrieval_quality_score": quality_score,
    }


# ---------------------------------------------------------------------------
# Node: analyze_identity
# ---------------------------------------------------------------------------

async def analyze_identity(state: AgentState) -> dict[str, Any]:
    """Analyze the identity record using LLM with retrieved context."""
    identity_record = state.get("identity_record")
    query = state.get("query", "")
    chunks = state.get("retrieved_chunks", [])
    tier = state.get("tier", "T3")

    # Build context string from retrieved chunks
    context_parts = []
    for i, chunk in enumerate(chunks[:5], 1):
        context_parts.append(
            f"[{i}] Source: {chunk['document_source']}\n{chunk['content']}"
        )
    context_text = "\n\n".join(context_parts) if context_parts else "No context retrieved."

    identity_summary = ""
    if identity_record:
        identity_summary = f"""
Agent Identity:
  - ID: {identity_record.get('id', 'unknown')}
  - Name: {identity_record.get('name', 'unknown')}
  - SPIFFE ID: {identity_record.get('spiffe_id', 'unknown')}
  - Tier: {identity_record.get('tier', 'unknown')}
  - Status: {identity_record.get('status', 'unknown')}
  - Capabilities: {', '.join(identity_record.get('capabilities', []))}
"""

    user_prompt = f"""Audit Query: {query}

{identity_summary}

Retrieved Context:
{context_text}

Provide a structured identity audit analysis. For each finding, cite the relevant
context source using [N] notation. Be specific about compliance and security implications."""

    model = os.getenv("LITELLM_MODEL", "vertex_ai/gemini-1.5-pro")

    try:
        response = await completion(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2048,
            temperature=0.0,
        )
        analysis = response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("LLM analysis failed: %s", exc)
        analysis = f"Analysis unavailable due to LLM error: {exc}"

    return {
        "messages": [
            HumanMessage(content=user_prompt),
            AIMessage(content=analysis),
        ],
        "final_report": analysis,
    }


# ---------------------------------------------------------------------------
# Node: generate_report
# ---------------------------------------------------------------------------

async def generate_report(state: AgentState) -> dict[str, Any]:
    """Format the analysis into a structured audit report."""
    analysis = state.get("final_report", "")
    identity_record = state.get("identity_record")
    session_id = state.get("session_id", "")
    chunks = state.get("retrieved_chunks", [])

    # Extract citations from analysis text ([1], [2], etc.)
    import re

    cited_indices = set(int(m) for m in re.findall(r"\[(\d+)\]", analysis))
    citations = []
    for idx in sorted(cited_indices):
        if 1 <= idx <= len(chunks):
            chunk = chunks[idx - 1]
            citations.append(f"[{idx}] {chunk['document_source']}")

    agent_name = identity_record.get("name", "Unknown Agent") if identity_record else "Unknown Agent"

    report = f"""# Identity Audit Report

**Session**: {session_id}
**Agent**: {agent_name}

## Analysis

{analysis}

## Citations

{chr(10).join(citations) if citations else "No citations."}

---
*This report was generated by the identity-auditor agent and is grounded in retrieved documentation.*
"""

    return {
        "final_report": report,
        "citations": citations,
    }


# ---------------------------------------------------------------------------
# Node: cite_sources
# ---------------------------------------------------------------------------

async def cite_sources(state: AgentState) -> dict[str, Any]:
    """
    Grounding check: verify that the report's claims are supported by
    retrieved chunks. Compute a grounding score.
    """
    report = state.get("final_report", "")
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        return {"grounding_score": 0.3, "requires_human_review": True}

    # Simple heuristic: check what fraction of key terms in the report
    # appear in the retrieved context
    report_words = set(report.lower().split())
    context_words: set[str] = set()
    for chunk in chunks:
        context_words.update(chunk["content"].lower().split())

    # Remove stopwords for meaningful overlap
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                 "have", "has", "had", "do", "does", "did", "will", "would",
                 "shall", "should", "may", "might", "must", "can", "could",
                 "for", "in", "on", "at", "to", "from", "with", "of", "and",
                 "or", "but", "not", "this", "that", "these", "those", "it"}
    report_content = report_words - stopwords
    overlap = report_content & context_words

    if len(report_content) > 0:
        grounding_score = len(overlap) / len(report_content)
    else:
        grounding_score = 0.5

    grounding_score = min(1.0, max(0.0, grounding_score))
    requires_human_review = grounding_score < GROUNDING_THRESHOLD

    return {
        "grounding_score": grounding_score,
        "requires_human_review": requires_human_review,
    }


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------

def should_retry_retrieval(state: AgentState) -> str:
    """After retrieve_context: decide whether to retry or proceed."""
    quality_score = state.get("retrieval_quality_score", 0.0)
    retry_count = state.get("retry_count", 0)

    if quality_score >= RETRIEVAL_QUALITY_THRESHOLD:
        return "proceed"
    elif retry_count < MAX_RETRIES:
        return "retry"
    else:
        return "proceed_degraded"


def should_flag_for_review(state: AgentState) -> str:
    """After cite_sources: decide whether output is ready or needs review."""
    requires_review = state.get("requires_human_review", False)
    return "flag_review" if requires_review else "complete"


# ---------------------------------------------------------------------------
# Retry node
# ---------------------------------------------------------------------------

async def increment_retry(state: AgentState) -> dict[str, Any]:
    """Increment retry counter and clear cached results for retry."""
    return {
        "retry_count": state.get("retry_count", 0) + 1,
        "retrieved_chunks": [],
        "retrieval_quality_score": 0.0,
    }


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------

def build_identity_audit_graph() -> Any:
    """Construct the LangGraph identity audit agent graph."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("retry_retrieval", increment_retry)
    workflow.add_node("analyze_identity", analyze_identity)
    workflow.add_node("generate_report", generate_report)
    workflow.add_node("cite_sources", cite_sources)

    # Entry point
    workflow.add_edge(START, "retrieve_context")

    # Conditional: after retrieval, retry or proceed
    workflow.add_conditional_edges(
        "retrieve_context",
        should_retry_retrieval,
        {
            "proceed": "analyze_identity",
            "retry": "retry_retrieval",
            "proceed_degraded": "analyze_identity",
        },
    )
    workflow.add_edge("retry_retrieval", "retrieve_context")

    # Linear: analyze → report → cite
    workflow.add_edge("analyze_identity", "generate_report")
    workflow.add_edge("generate_report", "cite_sources")

    # Final conditional: grounding check
    workflow.add_conditional_edges(
        "cite_sources",
        should_flag_for_review,
        {
            "complete": END,
            "flag_review": END,  # Still end, but requires_human_review=True signals caller
        },
    )

    return workflow.compile()


# Singleton compiled graph
identity_audit_graph = build_identity_audit_graph()
