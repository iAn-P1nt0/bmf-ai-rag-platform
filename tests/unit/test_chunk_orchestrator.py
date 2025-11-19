"""
Unit tests for Chunk Orchestrator
"""
import pytest
import json
from pathlib import Path
from agents.chunk_orchestrator.chunk_agent import ChunkOrchestrator


@pytest.fixture
def chunk_orchestrator(tmp_path):
    """Create a ChunkOrchestrator instance with temporary directories."""
    input_dir = tmp_path / "processed"
    cache_dir = tmp_path / "cache"

    input_dir.mkdir()
    cache_dir.mkdir()

    # Create minimal chunking config
    chunking_config = {
        "token_limits": {
            "max_tokens_per_chunk": 1200,
            "min_tokens_per_chunk": 100
        },
        "overlap": {
            "percentage": 25
        },
        "table_handling": {
            "preserve_verbatim": True
        }
    }

    chunking_config_path = tmp_path / "chunking.yml"
    import yaml
    with open(chunking_config_path, 'w') as f:
        yaml.dump(chunking_config, f)

    # Create minimal metadata schema
    metadata_schema = {
        "required": ["chunk_id", "fund_name", "category"]
    }

    metadata_schema_path = tmp_path / "metadata_schema.json"
    with open(metadata_schema_path, 'w') as f:
        json.dump(metadata_schema, f)

    diff_db_path = cache_dir / "diff.db"

    return ChunkOrchestrator(
        input_dir=str(input_dir),
        chunking_config_path=str(chunking_config_path),
        metadata_schema_path=str(metadata_schema_path),
        diff_db_path=str(diff_db_path)
    )


def test_chunk_orchestrator_initialization(chunk_orchestrator):
    """Test that Chunk Orchestrator initializes correctly."""
    assert chunk_orchestrator is not None
    assert chunk_orchestrator.chunking_config is not None
    assert chunk_orchestrator.metadata_schema is not None
    assert chunk_orchestrator.encoding is not None


def test_token_counting(chunk_orchestrator):
    """Test token counting functionality."""
    text = "This is a sample text for testing token counting."
    token_count = chunk_orchestrator.count_tokens(text)

    assert token_count > 0
    assert isinstance(token_count, int)


def test_create_chunks_from_html_document(chunk_orchestrator):
    """Test chunk creation from HTML document."""
    document = {
        'source_file': '/path/to/test.html',
        'file_type': 'html',
        'section': 'funds',
        'plain_text': "This is a test document. " * 100,  # Make it long enough to chunk
        'checksum': 'abc123',
        'extracted_data': {
            'fund_name': 'Test Fund'
        },
        'tables': []
    }

    chunks = chunk_orchestrator.create_chunks(document)

    assert len(chunks) > 0
    assert all('chunk_id' in chunk for chunk in chunks)
    assert all('content' in chunk for chunk in chunks)
    assert all('metadata' in chunk for chunk in chunks)
    assert all('checksum' in chunk for chunk in chunks)


def test_chunk_size_limits(chunk_orchestrator):
    """Test that chunks respect size limits."""
    # Create a very long document
    long_text = "Word " * 5000
    document = {
        'source_file': '/path/to/long.html',
        'file_type': 'html',
        'section': 'funds',
        'plain_text': long_text,
        'checksum': 'def456',
        'extracted_data': {},
        'tables': []
    }

    chunks = chunk_orchestrator.create_chunks(document)

    # Check that all chunks are within token limit
    max_tokens = chunk_orchestrator.chunking_config['token_limits']['max_tokens_per_chunk']

    for chunk in chunks:
        token_count = chunk_orchestrator.count_tokens(chunk['content'])
        assert token_count <= max_tokens, f"Chunk exceeds max tokens: {token_count} > {max_tokens}"


def test_table_chunk_creation(chunk_orchestrator):
    """Test that tables are preserved verbatim in separate chunks."""
    document = {
        'source_file': '/path/to/table.html',
        'file_type': 'html',
        'section': 'funds',
        'plain_text': 'Some text',
        'checksum': 'ghi789',
        'extracted_data': {},
        'tables': [
            {
                'index': 0,
                'markdown': '| NAV | Date |\n|-----|------|\n| 100 | 2025-01-15 |',
                'json': [{'NAV': 100, 'Date': '2025-01-15'}],
                'rows': 1,
                'columns': 2
            }
        ]
    }

    chunks = chunk_orchestrator.create_chunks(document)

    # Should have at least one table chunk
    table_chunks = [c for c in chunks if c['metadata'].get('has_table')]
    assert len(table_chunks) > 0

    # Check table chunk properties
    table_chunk = table_chunks[0]
    assert 'NAV' in table_chunk['content']
    assert table_chunk['metadata']['has_table'] is True


def test_chunk_diff_tracking(chunk_orchestrator, tmp_path):
    """Test chunk diff tracking with SQLite."""
    chunk = {
        'chunk_id': 'test-chunk-1',
        'content': 'Test content',
        'metadata': {
            'parent_document_id': 'doc123',
            'created_at': '2025-01-15T00:00:00Z'
        },
        'checksum': 'checksum123'
    }

    # First time should be 'new'
    status, version = chunk_orchestrator.check_chunk_diff(chunk)
    assert status == 'new'
    assert version == 1

    # Update checksum
    chunk_orchestrator.update_chunk_checksum(chunk, version)

    # Second time should be 'unchanged'
    status, version = chunk_orchestrator.check_chunk_diff(chunk)
    assert status == 'unchanged'
    assert version == 1

    # Change content
    chunk['checksum'] = 'checksum456'
    status, version = chunk_orchestrator.check_chunk_diff(chunk)
    assert status == 'updated'
    assert version == 2


def test_financial_metrics_detection(chunk_orchestrator):
    """Test detection of financial metrics in chunks."""
    assert chunk_orchestrator._detect_financial_metrics("NAV is 100.50")
    assert chunk_orchestrator._detect_financial_metrics("AUM of 1000 crores")
    assert chunk_orchestrator._detect_financial_metrics("3-year return is 15%")
    assert not chunk_orchestrator._detect_financial_metrics("This is general text")


def test_chunk_metadata_propagation(chunk_orchestrator):
    """Test that metadata is correctly propagated to chunks."""
    document = {
        'source_file': '/path/to/test.html',
        'file_type': 'html',
        'section': 'funds',
        'plain_text': 'Test content for metadata',
        'checksum': 'meta123',
        'extracted_data': {
            'fund_name': 'Bandhan Core Equity Fund',
            'nav_value': 45.23,
            'risk_profile': 'moderately_high'
        },
        'tables': []
    }

    chunks = chunk_orchestrator.create_chunks(document)

    assert len(chunks) > 0

    # Check that metadata is present
    for chunk in chunks:
        metadata = chunk['metadata']
        assert metadata['section'] == 'funds'
        assert metadata['file_type'] == 'html'
        assert 'chunk_index' in metadata


def test_stats_tracking(chunk_orchestrator, tmp_path):
    """Test that stats are correctly tracked."""
    # Create sample parsed document
    document_data = {
        'source_file': '/path/to/test.html',
        'file_type': 'html',
        'section': 'funds',
        'plain_text': 'Test content ' * 200,
        'checksum': 'stats123',
        'extracted_data': {},
        'tables': []
    }

    doc_file = chunk_orchestrator.input_dir / "funds" / "test.json"
    doc_file.parent.mkdir(parents=True, exist_ok=True)
    with open(doc_file, 'w') as f:
        json.dump(document_data, f)

    # Process document
    result = chunk_orchestrator.process_document(doc_file)

    # Check result
    assert 'chunks_created' in result
    assert result['chunks_created'] > 0
    assert chunk_orchestrator.stats['total_chunks'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
