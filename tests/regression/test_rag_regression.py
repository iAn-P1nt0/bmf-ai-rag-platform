"""
Regression Tests for BMF RAG Copilot
20 prompts spanning each site section per AGENTS.md
"""
import pytest
from src.rag_copilot.claude_rag_copilot import ClaudeRAGCopilot, ConfidenceLevel


# Test data: 20 regression prompts covering all site sections
REGRESSION_PROMPTS = [
    # Funds section (scheme profiles, NAV tables, risk-o-meters)
    {
        'query': 'What is the NAV of Bandhan Core Equity Fund?',
        'section': 'funds',
        'expected_keywords': ['nav', 'core equity', 'bandhan'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'Show me the risk profile of Bandhan Equity Fund',
        'section': 'funds',
        'expected_keywords': ['risk', 'equity'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'What is the AUM of Bandhan Tax Advantage Fund?',
        'section': 'funds',
        'expected_keywords': ['aum', 'tax advantage'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'List all equity funds offered by Bandhan Mutual Fund',
        'section': 'funds',
        'expected_keywords': ['equity', 'fund'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },

    # Downloads section (factsheets, KIMs, financial statements)
    {
        'query': 'Where can I find the latest factsheet for Bandhan Core Equity Fund?',
        'section': 'downloads',
        'expected_keywords': ['factsheet', 'download'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'Show me the KIM for debt funds',
        'section': 'downloads',
        'expected_keywords': ['kim', 'debt'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'Where are the annual financial statements?',
        'section': 'downloads',
        'expected_keywords': ['financial statement', 'annual'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'Provide the compliance report for Q4 2024',
        'section': 'downloads',
        'expected_keywords': ['compliance', 'report'],
        'min_confidence': ConfidenceLevel.LOW,
        'min_citations': 1
    },

    # About Us section (leadership, governance, AMC overview)
    {
        'query': 'Who are the board members of Bandhan AMC?',
        'section': 'about_us',
        'expected_keywords': ['board', 'leadership'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'Tell me about Bandhan Mutual Fund company overview',
        'section': 'about_us',
        'expected_keywords': ['bandhan', 'mutual fund', 'amc'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'What is the governance structure of Bandhan AMC?',
        'section': 'about_us',
        'expected_keywords': ['governance'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },

    # Investor Education section (calculators, learning modules)
    {
        'query': 'How does SIP calculator work?',
        'section': 'investor_education',
        'expected_keywords': ['sip', 'calculator'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'Explain what is mutual fund investment',
        'section': 'investor_education',
        'expected_keywords': ['mutual fund', 'investment'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'What are the benefits of SIP investing?',
        'section': 'investor_education',
        'expected_keywords': ['sip', 'benefit'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'How to calculate mutual fund returns?',
        'section': 'investor_education',
        'expected_keywords': ['calculate', 'return'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },

    # Newsroom section (press releases, announcements)
    {
        'query': 'What are the latest press releases from Bandhan Mutual Fund?',
        'section': 'newsroom',
        'expected_keywords': ['press release', 'news'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'Show me recent announcements',
        'section': 'newsroom',
        'expected_keywords': ['announcement'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 1
    },
    {
        'query': 'Any new fund launches in 2025?',
        'section': 'newsroom',
        'expected_keywords': ['fund', 'launch', 'new'],
        'min_confidence': ConfidenceLevel.LOW,
        'min_citations': 1
    },

    # Cross-section queries
    {
        'query': 'What is the performance of Bandhan Core Equity Fund over last 3 years?',
        'section': 'funds',
        'expected_keywords': ['performance', 'return', 'year'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 2,
        'expect_disclaimer': True
    },
    {
        'query': 'Compare Bandhan Equity Fund with benchmark',
        'section': 'funds',
        'expected_keywords': ['benchmark', 'compare'],
        'min_confidence': ConfidenceLevel.MEDIUM,
        'min_citations': 2,
        'expect_disclaimer': True
    }
]


@pytest.fixture
def rag_copilot():
    """Fixture for RAG copilot instance."""
    return ClaudeRAGCopilot()


@pytest.mark.parametrize('test_case', REGRESSION_PROMPTS)
def test_regression_prompt(rag_copilot, test_case):
    """
    Test each regression prompt for:
    - Confidence level meets minimum
    - Required citations present
    - Expected keywords in response
    - Disclaimers when required
    """
    query = test_case['query']

    # Execute query
    response = rag_copilot.query(query)

    # Check confidence level
    min_confidence = test_case['min_confidence']
    confidence_values = {
        ConfidenceLevel.HIGH: 3,
        ConfidenceLevel.MEDIUM: 2,
        ConfidenceLevel.LOW: 1,
        ConfidenceLevel.INSUFFICIENT: 0
    }

    actual_confidence_value = confidence_values[response.confidence]
    min_confidence_value = confidence_values[min_confidence]

    assert actual_confidence_value >= min_confidence_value, \
        f"Confidence {response.confidence.value} below minimum {min_confidence.value} for query: {query}"

    # Check citation count
    min_citations = test_case['min_citations']
    assert len(response.citations) >= min_citations, \
        f"Expected at least {min_citations} citations, got {len(response.citations)} for query: {query}"

    # Check expected keywords in response
    response_lower = response.answer.lower()
    for keyword in test_case['expected_keywords']:
        assert keyword.lower() in response_lower, \
            f"Expected keyword '{keyword}' not found in response for query: {query}"

    # Check disclaimer if required
    if test_case.get('expect_disclaimer', False):
        assert response.disclaimer, \
            f"Expected disclaimer for query: {query}"


def test_citation_match_rate(rag_copilot):
    """
    Test overall citation match rate across all regression prompts.
    Target: >90% citation match rate per CLAUDE.md
    """
    total_prompts = len(REGRESSION_PROMPTS)
    citation_matches = 0

    for test_case in REGRESSION_PROMPTS:
        response = rag_copilot.query(test_case['query'])

        # Citation match if we have minimum required citations
        if len(response.citations) >= test_case['min_citations']:
            citation_matches += 1

    citation_match_rate = citation_matches / total_prompts

    assert citation_match_rate >= 0.90, \
        f"Citation match rate {citation_match_rate:.2%} below target 90%"


def test_retrieval_accuracy_target(rag_copilot):
    """
    Test retrieval accuracy across regression set.
    Target: 80-85% relevance per CLAUDE.md Section 6
    """
    total_prompts = len(REGRESSION_PROMPTS)
    high_confidence_responses = 0

    for test_case in REGRESSION_PROMPTS:
        response = rag_copilot.query(test_case['query'])

        # Count responses with medium or high confidence
        if response.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]:
            high_confidence_responses += 1

    accuracy = high_confidence_responses / total_prompts

    assert accuracy >= 0.80, \
        f"Retrieval accuracy {accuracy:.2%} below target 80%"


def test_confidence_threshold_enforcement(rag_copilot):
    """
    Test that copilot refuses queries below confidence threshold.
    Threshold: 0.6 per CLAUDE.md Section 1
    """
    # Intentionally vague/out-of-scope query
    vague_query = "What is the weather today?"

    response = rag_copilot.query(vague_query)

    # Should return insufficient confidence
    assert response.confidence == ConfidenceLevel.INSUFFICIENT, \
        "Expected INSUFFICIENT confidence for out-of-scope query"

    # Should have refusal message
    assert "don't have sufficient information" in response.answer.lower() or \
           "cannot answer" in response.answer.lower(), \
           "Expected refusal message for low confidence query"


def test_personalized_advice_refusal(rag_copilot):
    """
    Test that copilot refuses personalized investment advice.
    Per CLAUDE.md Section 4: Disallow personalized investment advice
    """
    advice_queries = [
        "Should I invest in Bandhan Equity Fund?",
        "Which fund is best for me?",
        "Tell me where to invest my money"
    ]

    for query in advice_queries:
        response = rag_copilot.query(query)

        # Should contain refusal/reframing language
        response_lower = response.answer.lower()
        assert any(phrase in response_lower for phrase in [
            "cannot provide personalized",
            "informational guidance",
            "consult with a financial advisor",
            "not investment advice"
        ]), f"Expected advice refusal for query: {query}"


def test_disclaimer_inclusion(rag_copilot):
    """
    Test that disclaimers are included for performance queries.
    Per CLAUDE.md Section 3: Insert cautionary statements
    """
    performance_query = "What are the 3-year returns of Bandhan Core Equity Fund?"

    response = rag_copilot.query(performance_query)

    # Should include past performance disclaimer
    assert response.disclaimer, "Expected disclaimer for performance query"
    assert "past performance" in response.disclaimer.lower(), \
        "Expected past performance disclaimer"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
