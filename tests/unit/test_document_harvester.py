"""
Unit tests for Document Harvester Agent
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from agents.document_harvester.harvester_agent import DocumentHarvester


@pytest.fixture
def harvester(tmp_path, create_temp_config_files):
    """Create a DocumentHarvester instance."""
    html_dir = tmp_path / "html"
    output_dir = tmp_path / "pdf"
    html_dir.mkdir()
    output_dir.mkdir()

    return DocumentHarvester(
        site_map_path=str(create_temp_config_files['site_map']),
        html_dir=str(html_dir),
        output_dir=str(output_dir),
        s3_bucket=None
    )


def test_harvester_initialization(harvester):
    """Test DocumentHarvester initialization."""
    assert harvester is not None
    assert harvester.site_map is not None
    assert harvester.checksums_db is not None


def test_load_checksums_db(harvester):
    """Test loading checksums database."""
    assert isinstance(harvester.checksums_db, dict)


def test_calculate_checksum(harvester, tmp_path):
    """Test checksum calculation."""
    test_file = tmp_path / "test.pdf"
    test_file.write_text("test content")

    checksum = harvester._calculate_checksum(test_file)

    assert isinstance(checksum, str)
    assert len(checksum) == 64  # SHA-256 produces 64 hex characters


def test_extract_document_links(harvester):
    """Test extracting document links from HTML."""
    html_content = """
    <html>
        <body>
            <a href="/downloads/factsheet.pdf">Factsheet</a>
            <a href="kim.pdf">KIM Document</a>
            <a href="/downloads/report.xlsx">Excel Report</a>
            <a href="/page.html">Web Page</a>
        </body>
    </html>
    """

    base_url = "https://bandhanmutual.com"
    file_types = ["pdf", "xlsx"]

    documents = harvester.extract_document_links(html_content, base_url, file_types)

    # Should find PDF and XLSX files
    assert len(documents) >= 2
    assert any(doc['file_type'] == 'pdf' for doc in documents)
    assert any(doc['file_type'] == 'xlsx' for doc in documents)


def test_classify_document(harvester):
    """Test document classification based on patterns."""
    patterns = {
        "factsheet": ".*factsheet.*\\.pdf$",
        "kim": ".*kim.*\\.pdf$"
    }

    # Test factsheet classification
    doc_info = {
        'url': 'https://example.com/fund-factsheet.pdf',
        'link_text': 'Download Factsheet'
    }
    assert harvester.classify_document(doc_info, patterns) == 'factsheet'

    # Test KIM classification
    doc_info = {
        'url': 'https://example.com/kim.pdf',
        'link_text': 'KIM Document'
    }
    assert harvester.classify_document(doc_info, patterns) == 'kim'

    # Test unclassified
    doc_info = {
        'url': 'https://example.com/other.pdf',
        'link_text': 'Other Document'
    }
    assert harvester.classify_document(doc_info, patterns) == 'other'


@patch('agents.document_harvester.harvester_agent.requests.get')
def test_download_document(mock_get, harvester, tmp_path):
    """Test document download."""
    # Mock successful download
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_content = Mock(return_value=[b'PDF content chunk'])
    mock_get.return_value = mock_response

    url = "https://example.com/test.pdf"
    output_path = tmp_path / "test.pdf"

    import asyncio
    success = asyncio.run(harvester.download_document(url, output_path))

    assert success is True
    assert output_path.exists()


@patch('agents.document_harvester.harvester_agent.requests.get')
def test_download_document_failure(mock_get, harvester, tmp_path):
    """Test download failure handling."""
    # Mock failed download
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    url = "https://example.com/missing.pdf"
    output_path = tmp_path / "missing.pdf"

    import asyncio
    success = asyncio.run(harvester.download_document(url, output_path))

    assert success is False


def test_harvest_section_no_file_types(harvester):
    """Test harvesting section with no file types configured."""
    # Remove file_types from funds section
    harvester.site_map['sections']['funds']['file_types'] = []

    result = harvester.harvest_section('funds')

    assert result == []


def test_stats_tracking(harvester):
    """Test statistics tracking."""
    assert harvester.stats['total_documents'] == 0
    assert harvester.stats['new_documents'] == 0
    assert harvester.stats['updated_documents'] == 0
    assert harvester.stats['skipped_documents'] == 0


def test_save_checksums_db(harvester):
    """Test saving checksums database."""
    harvester.checksums_db['test_url'] = 'test_checksum'
    harvester._save_checksums_db()

    # Load and verify
    loaded_db = harvester._load_checksums_db()
    assert 'test_url' in loaded_db
    assert loaded_db['test_url'] == 'test_checksum'


def test_duplicate_detection(harvester):
    """Test that duplicates are detected via checksums."""
    url = "https://example.com/doc.pdf"
    checksum = "abc123"

    # First time - should be new
    harvester.checksums_db[url] = checksum
    assert url in harvester.checksums_db

    # Second time - should be detected as duplicate
    assert harvester.checksums_db[url] == checksum


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
