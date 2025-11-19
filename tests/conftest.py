"""
Pytest configuration and shared fixtures for BMF RAG Platform tests.
"""
import pytest
import json
import yaml
from pathlib import Path
from typing import Dict
import tempfile
import shutil


@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp(prefix="bmf_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_site_map():
    """Sample SITE_MAP configuration for testing."""
    return {
        "version": "1.0.0",
        "base_url": "https://bandhanmutual.com",
        "sections": {
            "funds": {
                "url_patterns": [
                    "https://bandhanmutual.com/funds",
                    "https://bandhanmutual.com/funds/*"
                ],
                "crawl_frequency": "daily",
                "priority": "high",
                "metadata": {
                    "category": "scheme_profiles",
                    "doc_type": "fund_details"
                },
                "selectors": {
                    "nav_table": ".nav-table",
                    "risk_ometer": ".risk-meter",
                    "fund_name": "h1.fund-name",
                    "aum": ".aum-value"
                },
                "discovered_urls": [
                    "https://bandhanmutual.com/funds/core-equity",
                    "https://bandhanmutual.com/funds/tax-advantage"
                ]
            },
            "downloads": {
                "url_patterns": [
                    "https://bandhanmutual.com/downloads"
                ],
                "file_types": ["pdf", "xlsx"],
                "patterns": {
                    "factsheet": ".*factsheet.*\\.pdf$",
                    "kim": ".*kim.*\\.pdf$"
                }
            }
        },
        "global_settings": {
            "respect_robots_txt": True,
            "rate_limit_rps": 2,
            "user_agent": "BMF-RAG-Bot/1.0",
            "timeout_seconds": 30,
            "max_retries": 3
        }
    }


@pytest.fixture
def sample_chunking_config():
    """Sample chunking configuration for testing."""
    return {
        "version": "1.0.0",
        "chunking_strategy": {
            "type": "structure_aware"
        },
        "token_limits": {
            "max_tokens_per_chunk": 1200,
            "min_tokens_per_chunk": 100,
            "target_tokens_per_chunk": 800
        },
        "overlap": {
            "percentage": 25,
            "min_overlap_tokens": 50,
            "max_overlap_tokens": 360
        },
        "chunking_rules": {
            "html": {
                "priority_elements": ["article", "section", "div.content"],
                "preserve_structure": ["table", "ul", "ol"],
                "split_on": ["h1", "h2", "h3"]
            },
            "pdf": {
                "logical_sections": ["heading", "paragraph", "table"],
                "preserve_tables": True,
                "preserve_page_numbers": True
            }
        },
        "table_handling": {
            "preserve_verbatim": True,
            "max_table_tokens": 800,
            "split_large_tables": True
        },
        "metadata_propagation": {
            "inherit_from_parent": True,
            "required_fields": [
                "fund_name", "category", "risk_profile",
                "doc_type", "publish_date", "crawler_version", "checksum"
            ]
        }
    }


@pytest.fixture
def sample_metadata_schema():
    """Sample metadata schema for testing."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "version": "1.0.0",
        "type": "object",
        "required": [
            "chunk_id", "fund_name", "category", "risk_profile",
            "doc_type", "publish_date", "crawler_version", "checksum"
        ],
        "properties": {
            "chunk_id": {
                "type": "string",
                "pattern": "^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
            },
            "fund_name": {"type": "string", "minLength": 1},
            "category": {
                "type": "string",
                "enum": ["scheme_profiles", "regulatory_documents", "education"]
            },
            "risk_profile": {
                "type": "string",
                "enum": ["low", "moderate", "moderately_high", "high"]
            }
        }
    }


@pytest.fixture
def sample_html_fund_page():
    """Sample HTML content for a fund page."""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Bandhan Core Equity Fund</title>
</head>
<body>
    <h1 class="fund-name">Bandhan Core Equity Fund - Regular Plan</h1>

    <div class="fund-overview">
        <p><strong>Category:</strong> Large Cap Equity</p>
        <p><strong>Risk Profile:</strong> <span class="risk-meter">Moderately High</span></p>
        <p><strong>Minimum Investment:</strong> Rs. 5,000</p>
    </div>

    <div class="aum-value">
        <strong>AUM:</strong> Rs. 5,234 crores (as of January 15, 2025)
    </div>

    <div class="fund-objective">
        <h2>Investment Objective</h2>
        <p>The fund seeks to generate long-term capital appreciation by investing
        primarily in equity and equity-related instruments of large-cap companies.
        The fund follows a growth-oriented investment strategy and benchmarks its
        performance against the Nifty 50 index.</p>
    </div>

    <div class="nav-table">
        <h2>NAV Performance</h2>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>NAV (Rs.)</th>
                    <th>Change</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>15-Jan-2025</td>
                    <td>45.23</td>
                    <td>+0.15</td>
                </tr>
                <tr>
                    <td>14-Jan-2025</td>
                    <td>45.08</td>
                    <td>-0.20</td>
                </tr>
                <tr>
                    <td>13-Jan-2025</td>
                    <td>45.28</td>
                    <td>+0.30</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="returns">
        <h2>Returns</h2>
        <table>
            <thead>
                <tr>
                    <th>Period</th>
                    <th>Fund Return (%)</th>
                    <th>Benchmark Return (%)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>1 Year</td>
                    <td>18.5</td>
                    <td>16.2</td>
                </tr>
                <tr>
                    <td>3 Years (CAGR)</td>
                    <td>14.2</td>
                    <td>13.8</td>
                </tr>
                <tr>
                    <td>5 Years (CAGR)</td>
                    <td>12.8</td>
                    <td>11.9</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="fund-manager">
        <h2>Fund Management</h2>
        <p><strong>Fund Manager:</strong> John Doe</p>
        <p><strong>Experience:</strong> 15 years</p>
    </div>

    <div class="holdings">
        <h2>Top Holdings</h2>
        <ul>
            <li>Reliance Industries Ltd - 8.5%</li>
            <li>HDFC Bank Ltd - 7.2%</li>
            <li>Infosys Ltd - 6.8%</li>
            <li>ICICI Bank Ltd - 5.9%</li>
            <li>TCS Ltd - 5.5%</li>
        </ul>
    </div>

    <div class="disclaimer">
        <p><em>Mutual fund investments are subject to market risks. Please read
        all scheme-related documents carefully before investing. Past performance
        is not indicative of future returns.</em></p>
    </div>
</body>
</html>
"""


@pytest.fixture
def sample_parsed_document():
    """Sample parsed document output."""
    return {
        "source_file": "/data/raw/html/funds/core_equity.html",
        "section": "funds",
        "parsed_at": "2025-01-20T00:00:00Z",
        "file_type": "html",
        "extracted_data": {
            "fund_name": "Bandhan Core Equity Fund - Regular Plan",
            "aum": "Rs. 5,234 crores (as of January 15, 2025)",
            "risk_ometer": "Moderately High"
        },
        "tables": [
            {
                "index": 0,
                "markdown": "| Date | NAV (Rs.) | Change |\n|------|-----------|--------|\n| 15-Jan-2025 | 45.23 | +0.15 |\n| 14-Jan-2025 | 45.08 | -0.20 |",
                "json": [
                    {"Date": "15-Jan-2025", "NAV (Rs.)": "45.23", "Change": "+0.15"},
                    {"Date": "14-Jan-2025", "NAV (Rs.)": "45.08", "Change": "-0.20"}
                ],
                "rows": 2,
                "columns": 3
            }
        ],
        "table_count": 2,
        "semantic_elements": [],
        "element_count": 0,
        "plain_text": "Bandhan Core Equity Fund - Regular Plan\n\nThe fund seeks to generate long-term capital appreciation...",
        "text_length": 1250,
        "checksum": "abc123def456"
    }


@pytest.fixture
def sample_chunk():
    """Sample chunk for testing."""
    return {
        "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
        "content": "The Bandhan Core Equity Fund is a large-cap equity fund that invests primarily in blue-chip companies. The fund has delivered consistent returns with a 3-year CAGR of 14.2%.",
        "metadata": {
            "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
            "parent_document_id": "abc123def456",
            "source_url": "/data/raw/html/funds/core_equity.html",
            "section": "funds",
            "file_type": "html",
            "chunk_index": 0,
            "created_at": "2025-01-20T00:00:00Z",
            "has_table": False,
            "has_financial_metrics": True,
            "fund_name": "Bandhan Core Equity Fund",
            "category": "scheme_profiles",
            "risk_profile": "moderately_high",
            "doc_type": "fund_details",
            "publish_date": "2025-01-15T00:00:00Z",
            "crawler_version": "v1.0.0",
            "checksum": "chunk_checksum_123"
        },
        "checksum": "chunk_content_checksum",
        "token_count": 45
    }


@pytest.fixture
def create_temp_config_files(tmp_path, sample_site_map, sample_chunking_config, sample_metadata_schema):
    """Create temporary configuration files for testing."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()

    # Site map
    site_map_dir = configs_dir / "site_map"
    site_map_dir.mkdir()
    site_map_path = site_map_dir / "SITE_MAP.json"
    with open(site_map_path, 'w') as f:
        json.dump(sample_site_map, f)

    # Chunking config
    chunking_dir = configs_dir / "chunking"
    chunking_dir.mkdir()
    chunking_path = chunking_dir / "chunking.yml"
    with open(chunking_path, 'w') as f:
        yaml.dump(sample_chunking_config, f)

    # Metadata schema
    metadata_dir = configs_dir / "metadata_schema"
    metadata_dir.mkdir()
    metadata_path = metadata_dir / "metadata_schema.json"
    with open(metadata_path, 'w') as f:
        json.dump(sample_metadata_schema, f)

    return {
        'site_map': site_map_path,
        'chunking': chunking_path,
        'metadata_schema': metadata_path
    }


@pytest.fixture
def create_temp_data_dirs(tmp_path):
    """Create temporary data directories for testing."""
    data_dir = tmp_path / "data"

    dirs = {
        'raw_html': data_dir / "raw" / "html",
        'raw_pdf': data_dir / "raw" / "pdf",
        'processed': data_dir / "processed",
        'cache': data_dir / "cache"
    }

    for dir_path in dirs.values():
        dir_path.mkdir(parents=True)

    return dirs


@pytest.fixture
def mock_agentset_client():
    """Mock AgentSet client for testing."""
    class MockAgentSetClient:
        def __init__(self):
            self.ingested_chunks = []

        def ingest(self, index, documents):
            self.ingested_chunks.extend(documents)
            return {
                'status': 'success',
                'chunks_ingested': len(documents),
                'index': index
            }

        def search(self, query, index, top_k=6):
            # Return mock search results
            return [
                {
                    'chunk_id': f'mock_chunk_{i}',
                    'content': f'Mock content for query: {query}',
                    'score': 0.9 - (i * 0.1)
                }
                for i in range(top_k)
            ]

    return MockAgentSetClient()


# Pytest hooks for custom behavior
def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add markers based on file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "regression" in str(item.fspath):
            item.add_marker(pytest.mark.regression)
