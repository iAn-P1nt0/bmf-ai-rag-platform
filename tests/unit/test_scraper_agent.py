"""
Unit tests for Scraper Agent
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from agents.scraper.scraper_agent import ScraperAgent, RateLimiter


@pytest.fixture
def scraper_agent(tmp_path, create_temp_config_files):
    """Create a ScraperAgent instance."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    return ScraperAgent(
        site_map_path=str(create_temp_config_files['site_map']),
        output_dir=str(output_dir),
        s3_bucket=None,
        rate_limit_rps=10.0,  # Fast for testing
        enable_screenshots=False
    )


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter(rate_limit_rps=2.0)
        assert limiter.rate_limit_rps == 2.0
        assert limiter.min_interval == 0.5

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_delay(self):
        """Test that rate limiter enforces minimum delay."""
        import time

        limiter = RateLimiter(rate_limit_rps=10.0)  # 100ms between requests

        start_time = time.time()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.time() - start_time

        # Should have at least min_interval delay
        assert elapsed >= limiter.min_interval


def test_scraper_agent_initialization(scraper_agent):
    """Test ScraperAgent initialization."""
    assert scraper_agent is not None
    assert scraper_agent.site_map is not None
    assert scraper_agent.rate_limiter is not None
    assert scraper_agent.stats['total_urls'] == 0


def test_load_site_map(scraper_agent):
    """Test loading SITE_MAP configuration."""
    assert 'funds' in scraper_agent.site_map['sections']
    assert scraper_agent.site_map['global_settings']['rate_limit_rps'] == 2


@pytest.mark.asyncio
@pytest.mark.slow
@patch('agents.scraper.scraper_agent.async_playwright')
async def test_scrape_page(mock_playwright, scraper_agent, sample_html_fund_page):
    """Test scraping a single page."""
    # Mock Playwright components
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value=sample_html_fund_page)
    mock_page.title = AsyncMock(return_value="Bandhan Core Equity Fund")
    mock_page.url = "https://bandhanmutual.com/funds/core-equity"
    mock_page.screenshot = AsyncMock()
    mock_page.query_selector = AsyncMock(return_value=None)

    url = "https://bandhanmutual.com/funds/core-equity"
    section = "funds"
    selectors = {"fund_name": "h1.fund-name"}

    metadata = await scraper_agent._scrape_page(mock_page, url, section, selectors)

    assert metadata['success'] is True
    assert metadata['url'] == url
    assert metadata['section'] == section
    assert 'title' in metadata
    assert 'content_hash' in metadata


@pytest.mark.asyncio
async def test_scrape_section_no_urls(scraper_agent):
    """Test scraping section with no discovered URLs."""
    # Clear discovered URLs
    scraper_agent.site_map['sections']['funds']['discovered_urls'] = []

    results = await scraper_agent.scrape_section('funds', url_limit=0)

    assert results == []
    assert scraper_agent.stats['total_urls'] == 0


def test_stats_tracking(scraper_agent):
    """Test statistics tracking."""
    assert scraper_agent.stats['total_urls'] == 0
    assert scraper_agent.stats['successful_scrapes'] == 0
    assert scraper_agent.stats['failed_scrapes'] == 0


@pytest.mark.asyncio
async def test_error_handling_invalid_url(scraper_agent):
    """Test error handling for invalid URLs."""
    with patch('agents.scraper.scraper_agent.async_playwright'):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=Exception("Invalid URL"))

        result = await scraper_agent._scrape_page(
            mock_page,
            "invalid-url",
            "funds",
            {}
        )

        assert result['success'] is False
        assert 'error' in result
        assert scraper_agent.stats['failed_scrapes'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
