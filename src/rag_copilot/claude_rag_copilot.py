"""
Claude RAG Copilot - BMF AI Assistant with grounded retrieval.
Based on CLAUDE.md specifications.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import anthropic
from loguru import logger


class InvestorType(Enum):
    """Investor type classification."""
    RETAIL = "retail"
    ADVISOR = "advisor"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    """Confidence level for responses."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


@dataclass
class RetrievalChunk:
    """Retrieved chunk with metadata."""
    chunk_id: str
    content: str
    source_url: str
    metadata: Dict
    score: float


@dataclass
class RAGResponse:
    """Structured RAG response."""
    answer: str
    confidence: ConfidenceLevel
    citations: List[Dict]
    investor_type: InvestorType
    disclaimer: str
    reasoning_steps: List[str]
    retrieval_chunks: List[RetrievalChunk]


class ClaudeRAGCopilot:
    """
    BMF RAG Copilot using Claude 3.5 Sonnet.

    Implements the 5-step reasoning pattern from CLAUDE.md:
    1. Clarify
    2. Retrieve
    3. Ground
    4. Validate
    5. Deliver
    """

    # Confidence threshold from CLAUDE.md
    CONFIDENCE_THRESHOLD = 0.6

    # Required citations
    MIN_CITATIONS = 2

    def __init__(
        self,
        api_key: Optional[str] = None,
        agentset_client = None,
        index_name: str = "bmf-rag-v1"
    ):
        """
        Initialize Claude RAG Copilot.

        Args:
            api_key: Anthropic API key
            agentset_client: AgentSet client for retrieval
            index_name: AgentSet index name
        """
        self.client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )
        self.agentset_client = agentset_client
        self.index_name = index_name
        self.model = "claude-3-5-sonnet-20241022"

    def _build_system_prompt(self) -> str:
        """Build system prompt based on CLAUDE.md mission."""
        return """You are the Bandhan Mutual Fund (BMF) RAG copilot, an expert assistant for asset-management queries.

MISSION:
- Answer queries using ONLY grounded evidence from the provided knowledge base
- Focus on: scheme insights, downloads, regulatory updates, investor education, corporate news, fund performance
- NEVER hallucinate - always cite sources
- Surface confidence level with every response
- Refuse to answer when retrieval confidence < 0.6

CONTRACT:
- Never provide personalized investment advice; offer informational guidance only
- Explain financial jargon in plain English
- Use Indian numbering (crores/lakhs) when presenting numbers
- Include as-of dates for all figures
- Add cautionary statements for performance comparisons
- Cite at least 2 unique sources when available

TONE:
- Advisory, professional, and helpful
- Plain-English explanations
- Concise yet comprehensive

DISCLAIMER REQUIREMENTS:
- Past performance disclaimers for 3+ year data
- Risk disclosures for scheme recommendations
- Regulatory compliance statements when needed"""

    def step1_clarify(self, query: str) -> Tuple[str, InvestorType]:
        """
        Step 1: Clarify ambiguous prompts and detect investor type.

        Args:
            query: User query

        Returns:
            Clarified query and investor type
        """
        logger.info("Step 1: Clarifying query...")

        # Detect investor type from query patterns
        investor_type = InvestorType.UNKNOWN
        query_lower = query.lower()

        if any(word in query_lower for word in ['client', 'portfolio', 'advisory', 'recommend']):
            investor_type = InvestorType.ADVISOR
        elif any(word in query_lower for word in ['internal', 'operations', 'compliance', 'team']):
            investor_type = InvestorType.INTERNAL
        elif any(word in query_lower for word in ['i want', 'should i', 'my investment', 'help me']):
            investor_type = InvestorType.RETAIL
        else:
            investor_type = InvestorType.RETAIL  # Default to retail

        # For now, return query as-is (could use Claude to reformulate)
        clarified_query = query

        logger.info(f"Detected investor type: {investor_type.value}")

        return clarified_query, investor_type

    def step2_retrieve(self, query: str, top_k: int = 6) -> List[RetrievalChunk]:
        """
        Step 2: Retrieve top-k chunks with hybrid scoring.

        Args:
            query: Search query
            top_k: Number of chunks to retrieve

        Returns:
            List of retrieved chunks
        """
        logger.info(f"Step 2: Retrieving top {top_k} chunks...")

        # Mock retrieval for now - replace with actual AgentSet call
        # In production: self.agentset_client.search(query, index=self.index_name, top_k=top_k)

        mock_chunks = [
            RetrievalChunk(
                chunk_id="chunk_001",
                content="Bandhan Core Equity Fund has an AUM of ₹5,234 crores as of January 15, 2025. The fund follows a large-cap focused investment strategy with Nifty 50 as its benchmark.",
                source_url="https://bandhanmutual.com/funds/core-equity",
                metadata={
                    "fund_name": "Bandhan Core Equity Fund",
                    "category": "scheme_profiles",
                    "risk_profile": "moderately_high",
                    "doc_type": "fund_details",
                    "publish_date": "2025-01-15T00:00:00Z",
                    "nav_date": "2025-01-15"
                },
                score=0.89
            ),
            RetrievalChunk(
                chunk_id="chunk_002",
                content="The fund's NAV as of January 15, 2025 is ₹45.23. Year-to-date returns stand at 3.2%, with 1-year returns at 18.5% and 3-year CAGR at 14.2%.",
                source_url="https://bandhanmutual.com/funds/core-equity",
                metadata={
                    "fund_name": "Bandhan Core Equity Fund",
                    "category": "performance_data",
                    "doc_type": "nav_table",
                    "publish_date": "2025-01-15T00:00:00Z"
                },
                score=0.85
            )
        ]

        logger.info(f"Retrieved {len(mock_chunks)} chunks")
        return mock_chunks

    def step3_ground(self, query: str, chunks: List[RetrievalChunk]) -> str:
        """
        Step 3: Ground draft with key figures and citations.

        Args:
            query: Original query
            chunks: Retrieved chunks

        Returns:
            Grounded draft response
        """
        logger.info("Step 3: Grounding response with retrieved context...")

        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(f"""
Source {i} (ID: {chunk.chunk_id}, Score: {chunk.score:.2f}):
URL: {chunk.source_url}
Metadata: {json.dumps(chunk.metadata, indent=2)}
Content: {chunk.content}
""")

        context = "\n".join(context_parts)

        # Create grounding prompt
        prompt = f"""Based ONLY on the following retrieved sources, answer this query: "{query}"

Retrieved Sources:
{context}

Instructions:
1. Lead with a direct answer to the query
2. Include specific figures with as-of dates
3. Cite at least 2 unique sources using [Source N] notation
4. Use Indian numbering (crores/lakhs) for currency
5. Explain any jargon briefly
6. If information is insufficient, clearly state what's missing

Draft your response now:"""

        # Call Claude for grounding
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=self._build_system_prompt(),
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        draft = message.content[0].text
        logger.info("Grounded draft created")

        return draft

    def step4_validate(
        self,
        draft: str,
        chunks: List[RetrievalChunk],
        investor_type: InvestorType
    ) -> Tuple[str, List[str]]:
        """
        Step 4: Validate against policy rules.

        Args:
            draft: Draft response
            chunks: Retrieved chunks
            investor_type: Detected investor type

        Returns:
            Validated draft and list of required disclaimers
        """
        logger.info("Step 4: Validating response against policies...")

        disclaimers = []

        # Check for performance data requiring disclaimers
        if any(word in draft.lower() for word in ['return', 'performance', 'cagr', '%']):
            disclaimers.append(self._get_disclaimer('past_performance'))

        # Check for risk-related content
        if any(word in draft.lower() for word in ['risk', 'volatile', 'fluctuat']):
            disclaimers.append(self._get_disclaimer('risk_disclosure'))

        # Check if this is personalized advice (should refuse)
        if investor_type == InvestorType.RETAIL and any(
            word in draft.lower() for word in ['you should invest', 'i recommend', 'best for you']
        ):
            # Reframe the response
            validated = "I cannot provide personalized investment advice. However, I can share informational guidance about BMF schemes. " + draft
        else:
            validated = draft

        logger.info(f"Validation complete: {len(disclaimers)} disclaimers added")

        return validated, disclaimers

    def step5_deliver(
        self,
        validated_response: str,
        disclaimers: List[str],
        chunks: List[RetrievalChunk],
        investor_type: InvestorType
    ) -> RAGResponse:
        """
        Step 5: Deliver concise narrative with citations and disclaimers.

        Args:
            validated_response: Validated response
            disclaimers: Required disclaimers
            chunks: Retrieved chunks
            investor_type: Investor type

        Returns:
            Complete RAG response
        """
        logger.info("Step 5: Delivering final response...")

        # Calculate confidence based on retrieval scores
        avg_score = sum(c.score for c in chunks) / len(chunks) if chunks else 0

        if avg_score >= 0.8:
            confidence = ConfidenceLevel.HIGH
        elif avg_score >= self.CONFIDENCE_THRESHOLD:
            confidence = ConfidenceLevel.MEDIUM
        elif avg_score >= 0.4:
            confidence = ConfidenceLevel.LOW
        else:
            confidence = ConfidenceLevel.INSUFFICIENT

        # Extract citations
        citations = [
            {
                'chunk_id': chunk.chunk_id,
                'source_url': chunk.source_url,
                'fund_name': chunk.metadata.get('fund_name'),
                'doc_type': chunk.metadata.get('doc_type'),
                'score': chunk.score
            }
            for chunk in chunks
        ]

        # Build final answer
        disclaimer_text = "\n\n".join(disclaimers) if disclaimers else ""
        final_answer = f"{validated_response}\n\n{disclaimer_text}" if disclaimer_text else validated_response

        # Add call-to-action
        cta = "\n\nFor more details, visit bandhanmutual.com or consult with a financial advisor."
        final_answer += cta

        response = RAGResponse(
            answer=final_answer,
            confidence=confidence,
            citations=citations,
            investor_type=investor_type,
            disclaimer=disclaimer_text,
            reasoning_steps=[
                "Clarified query and detected investor type",
                f"Retrieved {len(chunks)} relevant chunks",
                "Grounded response with citations",
                "Validated against compliance policies",
                "Delivered final response with disclaimers"
            ],
            retrieval_chunks=chunks
        )

        logger.info(f"Response delivered with confidence: {confidence.value}")

        return response

    def query(self, user_query: str) -> RAGResponse:
        """
        Process a user query through the full 5-step RAG pipeline.

        Args:
            user_query: User's question

        Returns:
            Complete RAG response
        """
        logger.info(f"Processing query: {user_query}")

        # Step 1: Clarify
        clarified_query, investor_type = self.step1_clarify(user_query)

        # Step 2: Retrieve
        chunks = self.step2_retrieve(clarified_query)

        # Check confidence threshold
        if not chunks or all(c.score < self.CONFIDENCE_THRESHOLD for c in chunks):
            return RAGResponse(
                answer="I don't have sufficient information to answer your query with confidence. Please provide more details or rephrase your question.",
                confidence=ConfidenceLevel.INSUFFICIENT,
                citations=[],
                investor_type=investor_type,
                disclaimer="",
                reasoning_steps=["Query processed but confidence threshold not met"],
                retrieval_chunks=[]
            )

        # Step 3: Ground
        draft = self.step3_ground(clarified_query, chunks)

        # Step 4: Validate
        validated, disclaimers = self.step4_validate(draft, chunks, investor_type)

        # Step 5: Deliver
        response = self.step5_deliver(validated, disclaimers, chunks, investor_type)

        return response

    def _get_disclaimer(self, disclaimer_type: str) -> str:
        """Get disclaimer text by type."""
        disclaimers = {
            'past_performance': """
⚠️ Disclaimer: Past performance is not indicative of future results. Mutual fund investments are subject to market risks. Please read all scheme-related documents carefully before investing.""",
            'risk_disclosure': """
⚠️ Risk Disclosure: Mutual fund investments are subject to market risks. The NAV of the scheme may go up or down depending upon the factors and forces affecting the securities market.""",
            'kyc_reminder': """
📋 KYC Reminder: KYC (Know Your Customer) is a one-time exercise for securities market participants. Please ensure your KYC is complete before investing."""
        }
        return disclaimers.get(disclaimer_type, "")

    def fetch_nav_history(self, fund_id: str, lookback_days: int = 30) -> Dict:
        """
        Fetch NAV history for time-series outputs.

        Args:
            fund_id: Fund identifier
            lookback_days: Number of days to look back

        Returns:
            NAV history data
        """
        # Mock implementation - replace with actual data source
        logger.info(f"Fetching NAV history for {fund_id} (last {lookback_days} days)")

        return {
            'fund_id': fund_id,
            'lookback_days': lookback_days,
            'nav_data': [
                {'date': '2025-01-15', 'nav': 45.23},
                {'date': '2025-01-14', 'nav': 45.10},
                {'date': '2025-01-13', 'nav': 44.98}
            ]
        }

    def trigger_ops_alert(self, payload: Dict):
        """
        Trigger operational alert for escalation.

        Args:
            payload: Alert details
        """
        logger.warning(f"Triggering ops alert: {payload}")

        # In production, send to ops-alert@bmf.ai
        alert_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'severity': payload.get('severity', 'medium'),
            'message': payload.get('message'),
            'context': payload.get('context', {})
        }

        logger.info(f"Alert sent: {json.dumps(alert_data)}")


def main():
    """Demo usage of Claude RAG Copilot."""
    copilot = ClaudeRAGCopilot()

    # Example queries
    queries = [
        "What is the NAV of Bandhan Core Equity Fund?",
        "Show me the latest factsheet for debt funds",
        "Should I invest in Bandhan Tax Advantage Fund?"
    ]

    for query in queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print('='*80)

        response = copilot.query(query)

        print(f"\nConfidence: {response.confidence.value}")
        print(f"Investor Type: {response.investor_type.value}")
        print(f"\nAnswer:\n{response.answer}")
        print(f"\nCitations ({len(response.citations)}):")
        for citation in response.citations:
            print(f"  - {citation['source_url']} (chunk: {citation['chunk_id']}, score: {citation['score']:.2f})")


if __name__ == "__main__":
    main()
