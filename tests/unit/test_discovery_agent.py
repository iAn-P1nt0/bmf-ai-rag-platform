"""
Unit tests for Discovery Agent
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from agents.discovery.discovery_agent import DiscoveryAgent


@pytest.fixture
def discovery_agent(tmp_path, sample_site_map):
    """Create a DiscoveryAgent instance with temporary config."""
    config_path = tmp_path / "SITE_MAP.json"
    with open(config_path, 'w') as f:
        json.dump(sample_site_map, f)

    return DiscoveryAgent(
        config_path=str(config_path),
        output_path=str(config_path)
    )


def test_discovery_agent_initialization(discovery_agent, sample_site_map):
    """Test that Discovery Agent initializes correctly."""
    assert discovery_agent is not None
    assert discovery_agent.site_map is not None
    assert discovery_agent.site_map['base_url'] == sample_site_map['base_url']
    assert len(discovery_agent.site_map['sections']) == 2


def test_load_site_map(discovery_agent):
    """Test loading SITE_MAP configuration."""
    assert 'funds' in discovery_agent.site_map['sections']
    assert 'downloads' in discovery_agent.site_map['sections']
    assert discovery_agent.site_map['global_settings']['rate_limit_rps'] == 2


def test_matches_patterns(discovery_agent):
    """Test URL pattern matching."""
    # Test exact match
    assert discovery_agent._matches_patterns(
        "https://bandhanmutual.com/funds",
        ["https://bandhanmutual.com/funds"]
    )

    # Test wildcard match
    assert discovery_agent._matches_patterns(
        "https://bandhanmutual.com/funds/core-equity",
        ["https://bandhanmutual.com/funds/*"]
    )

    # Test no match
    assert not discovery_agent._matches_patterns(
        "https://example.com/other",
        ["https://bandhanmutual.com/funds/*"]
    )


def test_detect_changes(discovery_agent):
    """Test detection of URL changes."""
    current_urls = {
        "https://bandhanmutual.com/funds/core-equity",
        "https://bandhanmutual.com/funds/tax-advantage",
        "https://bandhanmutual.com/funds/balanced"
    }

    previous_urls = {
        "https://bandhanmutual.com/funds/core-equity",
        "https://bandhanmutual.com/funds/tax-advantage"
    }

    changes = discovery_agent.detect_changes("funds", current_urls, previous_urls)

    assert len(changes['new']) == 1
    assert "https://bandhanmutual.com/funds/balanced" in changes['new']
    assert len(changes['removed']) == 0
    assert len(changes['unchanged']) == 2


@patch('agents.discovery.discovery_agent.requests.get')
def test_fetch_sitemap_xml(mock_get, discovery_agent):
    """Test fetching and parsing sitemap.xml."""
    # Mock sitemap XML response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'''<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://bandhanmutual.com/funds/core-equity</loc>
        </url>
        <url>
            <loc>https://bandhanmutual.com/funds/tax-advantage</loc>
        </url>
    </urlset>'''
    mock_get.return_value = mock_response

    urls = discovery_agent.fetch_sitemap_xml("https://bandhanmutual.com")

    assert len(urls) >= 2
    assert any("core-equity" in url for url in urls)


def test_parse_sitemap_xml(discovery_agent):
    """Test parsing sitemap XML content."""
    xml_content = b'''<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://bandhanmutual.com/funds/fund1</loc>
        </url>
        <url>
            <loc>https://bandhanmutual.com/funds/fund2</loc>
        </url>
        <url>
            <loc>https://bandhanmutual.com/funds/fund3</loc>
        </url>
    </urlset>'''

    urls = discovery_agent._parse_sitemap_xml(xml_content)

    assert len(urls) == 3
    assert "https://bandhanmutual.com/funds/fund1" in urls
    assert "https://bandhanmutual.com/funds/fund2" in urls
    assert "https://bandhanmutual.com/funds/fund3" in urls


def test_parse_robots_txt(discovery_agent):
    """Test parsing robots.txt for sitemap URLs."""
    robots_content = """
User-agent: *
Disallow: /admin/
Sitemap: https://bandhanmutual.com/sitemap.xml
Sitemap: https://bandhanmutual.com/sitemap_index.xml
"""

    urls = discovery_agent._parse_robots_txt(robots_content)

    assert len(urls) == 2
    assert "https://bandhanmutual.com/sitemap.xml" in urls
    assert "https://bandhanmutual.com/sitemap_index.xml" in urls


@patch('agents.discovery.discovery_agent.requests.get')
def test_discover_urls_by_crawl(mock_get, discovery_agent):
    """Test URL discovery by crawling."""
    # Mock HTML response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'''
    <html>
        <body>
            <a href="/funds/core-equity">Core Equity Fund</a>
            <a href="/funds/tax-advantage">Tax Advantage Fund</a>
            <a href="/downloads/factsheet.pdf">Factsheet</a>
        </body>
    </html>'''
    mock_get.return_value = mock_response

    patterns = ["https://bandhanmutual.com/funds/*"]
    discovered = discovery_agent.discover_urls_by_crawl(
        "https://bandhanmutual.com/funds",
        patterns,
        max_depth=1
    )

    assert isinstance(discovered, set)
    # Should discover matching URLs
    assert any("funds" in url for url in discovered)


def test_save_site_map(discovery_agent, tmp_path):
    """Test saving updated SITE_MAP."""
    # Modify site map
    discovery_agent.site_map['sections']['funds']['url_count'] = 10

    # Save
    discovery_agent._save_site_map()

    # Load and verify
    with open(discovery_agent.output_path, 'r') as f:
        saved_map = json.load(f)

    assert saved_map['sections']['funds']['url_count'] == 10
    assert 'last_updated' in saved_map


def test_run_discovery_creates_backup(discovery_agent, tmp_path):
    """Test that discovery creates backup before updating."""
    # Create initial state
    discovery_agent._save_site_map()

    # Run discovery (will create backup)
    with patch('agents.discovery.discovery_agent.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<urlset></urlset>'
        mock_get.return_value = mock_response

        discovery_agent.run_discovery()

    # Check that backup was created
    backup_files = list(discovery_agent.output_path.parent.glob("SITE_MAP_backup_*.json"))
    assert len(backup_files) > 0


def test_stats_tracking(discovery_agent):
    """Test that discovery tracks statistics correctly."""
    current_urls = {"url1", "url2", "url3"}
    previous_urls = {"url1", "url2"}

    changes = discovery_agent.detect_changes("funds", current_urls, previous_urls)

    assert len(changes['new']) == 1
    assert len(changes['unchanged']) == 2


@pytest.mark.slow
@patch('agents.discovery.discovery_agent.requests.get')
def test_discovery_with_multiple_sections(mock_get, discovery_agent):
    """Test discovery across multiple sections."""
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'<urlset></urlset>'
    mock_get.return_value = mock_response

    report = discovery_agent.run_discovery()

    assert 'timestamp' in report
    assert 'total_sections' in report
    assert report['total_sections'] == 2  # funds and downloads


def test_error_handling_missing_config(tmp_path):
    """Test error handling when config file is missing."""
    with pytest.raises(FileNotFoundError):
        DiscoveryAgent(config_path=str(tmp_path / "missing.json"))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
