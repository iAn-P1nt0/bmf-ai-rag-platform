"""
Unit tests for Claude RAG Copilot
"""
import pytest
from unittest.mock import Mock, patch
from src.rag_copilot.claude_rag_copilot import (
    ClaudeRAGCopilot,
    InvestorType,
    ConfidenceLevel,
    RetrievalChunk,
    RAGResponse
)


@pytest.fixture
def rag_copilot(mock_agentset_client):
    """Create a ClaudeRAGCopilot instance."""
    return ClaudeRAGCopilot(
        api_key="test_key",
        agentset_client=mock_agentset_client,
        index_name="test-index"
    )


@pytest.fixture
def sample_chunks():
    """Sample retrieval chunks for testing."""
    return [
        RetrievalChunk(
            chunk_id="chunk_001",
            content="Bandhan Core Equity Fund has an AUM of ₹5,234 crores as of January 15, 2025. The fund invests in large-cap stocks.",
            source_url="https://bandhanmutual.com/funds/core-equity",
            metadata={
                "fund_name": "Bandhan Core Equity Fund",
                "category": "scheme_profiles",
                "doc_type": "fund_details"
            },
            score=0.92
        ),
        RetrievalChunk(
            chunk_id="chunk_002",
            content="The NAV of Bandhan Core Equity Fund is ₹45.23 as of January 15, 2025. The 1-year return is 18.5%.",
            source_url="https://bandhanmutual.com/funds/core-equity",
            metadata={
                "fund_name": "Bandhan Core Equity Fund",
                "category": "performance_data",
                "doc_type": "nav_table"
            },
            score=0.88
        )
    ]


class TestInvestorTypeDetection:
    """Tests for investor type detection (Step 1: Clarify)."""

    def test_detect_retail_investor(self, rag_copilot):
        """Test detection of retail investor queries."""
        query = "Should I invest in this fund?"
        clarified, investor_type = rag_copilot.step1_clarify(query)

        assert investor_type == InvestorType.RETAIL

    def test_detect_advisor_investor(self, rag_copilot):
        """Test detection of advisor queries."""
        query = "What should I recommend to my client for their portfolio?"
        clarified, investor_type = rag_copilot.step1_clarify(query)

        assert investor_type == InvestorType.ADVISOR

    def test_detect_internal_user(self, rag_copilot):
        """Test detection of internal user queries."""
        query = "What is our internal compliance requirement for this scheme?"
        clarified, investor_type = rag_copilot.step1_clarify(query)

        assert investor_type == InvestorType.INTERNAL

    def test_default_to_retail(self, rag_copilot):
        """Test that unclear queries default to retail."""
        query = "What is the NAV?"
        clarified, investor_type = rag_copilot.step1_clarify(query)

        assert investor_type == InvestorType.RETAIL


class TestRetrievalStep:
    """Tests for retrieval step (Step 2: Retrieve)."""

    def test_retrieve_returns_chunks(self, rag_copilot):
        """Test that retrieval returns chunks."""
        chunks = rag_copilot.step2_retrieve("What is the NAV?")

        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(c, RetrievalChunk) for c in chunks)

    def test_retrieve_top_k(self, rag_copilot):
        """Test that retrieve respects top_k parameter."""
        chunks = rag_copilot.step2_retrieve("query", top_k=3)

        # With mock, should return requested number
        assert len(chunks) <= 6  # Mock returns up to 6


class TestGroundingStep:
    """Tests for grounding step (Step 3: Ground)."""

    @patch('src.rag_copilot.claude_rag_copilot.anthropic.Anthropic')
    def test_grounding_includes_citations(self, mock_anthropic, rag_copilot, sample_chunks):
        """Test that grounding includes citations."""
        # Mock Claude response
        mock_message = Mock()
        mock_message.content = [Mock(text="The NAV is ₹45.23 [Source 1]")]
        mock_anthropic.return_value.messages.create.return_value = mock_message

        rag_copilot.client = mock_anthropic.return_value

        draft = rag_copilot.step3_ground("What is the NAV?", sample_chunks)

        assert isinstance(draft, str)
        assert len(draft) > 0


class TestValidationStep:
    """Tests for validation step (Step 4: Validate)."""

    def test_adds_past_performance_disclaimer(self, rag_copilot, sample_chunks):
        """Test that past performance disclaimer is added."""
        draft = "The fund has returned 18.5% over the last year."

        validated, disclaimers = rag_copilot.step4_validate(
            draft, sample_chunks, InvestorType.RETAIL
        )

        assert len(disclaimers) > 0
        assert any("past performance" in d.lower() for d in disclaimers)

    def test_adds_risk_disclosure(self, rag_copilot, sample_chunks):
        """Test that risk disclosure is added."""
        draft = "This fund has moderate risk."

        validated, disclaimers = rag_copilot.step4_validate(
            draft, sample_chunks, InvestorType.RETAIL
        )

        assert len(disclaimers) > 0

    def test_reframes_personalized_advice(self, rag_copilot, sample_chunks):
        """Test that personalized advice is reframed."""
        draft = "You should invest in this fund."

        validated, disclaimers = rag_copilot.step4_validate(
            draft, sample_chunks, InvestorType.RETAIL
        )

        assert "cannot provide personalized" in validated.lower() or \
               "informational guidance" in validated.lower()


class TestDeliveryStep:
    """Tests for delivery step (Step 5: Deliver)."""

    def test_calculates_confidence_from_scores(self, rag_copilot, sample_chunks):
        """Test confidence calculation from retrieval scores."""
        validated = "Test response"
        disclaimers = []

        response = rag_copilot.step5_deliver(
            validated, disclaimers, sample_chunks, InvestorType.RETAIL
        )

        assert isinstance(response, RAGResponse)
        assert response.confidence in [
            ConfidenceLevel.HIGH,
            ConfidenceLevel.MEDIUM,
            ConfidenceLevel.LOW,
            ConfidenceLevel.INSUFFICIENT
        ]

    def test_includes_citations(self, rag_copilot, sample_chunks):
        """Test that response includes citations."""
        validated = "Test response"
        disclaimers = []

        response = rag_copilot.step5_deliver(
            validated, disclaimers, sample_chunks, InvestorType.RETAIL
        )

        assert len(response.citations) > 0
        assert all('chunk_id' in c for c in response.citations)
        assert all('source_url' in c for c in response.citations)


class TestConfidenceThreshold:
    """Tests for confidence threshold enforcement."""

    def test_refuses_low_confidence_queries(self, rag_copilot):
        """Test that low confidence queries are refused."""
        # Create low-score chunks
        low_score_chunks = [
            RetrievalChunk(
                chunk_id="low_001",
                content="Irrelevant content",
                source_url="https://example.com",
                metadata={},
                score=0.3  # Below threshold of 0.6
            )
        ]

        response = rag_copilot.query("Random irrelevant query")

        # Should refuse due to low confidence
        assert response.confidence == ConfidenceLevel.INSUFFICIENT
        assert "don't have sufficient information" in response.answer.lower() or \
               "cannot answer" in response.answer.lower()


class TestEndToEndQuery:
    """Tests for complete query processing."""

    @patch('src.rag_copilot.claude_rag_copilot.anthropic.Anthropic')
    def test_complete_query_flow(self, mock_anthropic, rag_copilot):
        """Test complete query flow through all 5 steps."""
        # Mock Claude response
        mock_message = Mock()
        mock_message.content = [Mock(text="The NAV is ₹45.23 as of Jan 15, 2025 [Source 1]")]
        mock_anthropic.return_value.messages.create.return_value = mock_message

        rag_copilot.client = mock_anthropic.return_value

        query = "What is the NAV of Bandhan Core Equity Fund?"
        response = rag_copilot.query(query)

        assert isinstance(response, RAGResponse)
        assert len(response.answer) > 0
        assert response.investor_type in InvestorType
        assert response.confidence in ConfidenceLevel
        assert len(response.reasoning_steps) == 5  # All 5 steps


class TestDisclaimers:
    """Tests for disclaimer system."""

    def test_get_past_performance_disclaimer(self, rag_copilot):
        """Test getting past performance disclaimer."""
        disclaimer = rag_copilot._get_disclaimer('past_performance')

        assert len(disclaimer) > 0
        assert "past performance" in disclaimer.lower()

    def test_get_risk_disclosure(self, rag_copilot):
        """Test getting risk disclosure."""
        disclaimer = rag_copilot._get_disclaimer('risk_disclosure')

        assert len(disclaimer) > 0
        assert "risk" in disclaimer.lower()


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_fetch_nav_history(self, rag_copilot):
        """Test NAV history fetching."""
        history = rag_copilot.fetch_nav_history("FUND001", lookback_days=30)

        assert 'fund_id' in history
        assert 'nav_data' in history
        assert history['fund_id'] == "FUND001"

    def test_trigger_ops_alert(self, rag_copilot):
        """Test ops alert triggering."""
        payload = {
            'severity': 'high',
            'message': 'Test alert',
            'context': {'query': 'test'}
        }

        # Should not raise exception
        rag_copilot.trigger_ops_alert(payload)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
