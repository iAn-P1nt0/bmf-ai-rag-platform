"""
Performance tests for Chunking operations
"""
import pytest
import time
from agents.chunk_orchestrator.chunk_agent import ChunkOrchestrator


@pytest.fixture
def large_document():
    """Create a large document for performance testing."""
    return {
        'source_file': '/path/to/large_doc.html',
        'file_type': 'html',
        'section': 'funds',
        'plain_text': "This is a test sentence. " * 10000,  # ~100KB of text
        'checksum': 'large_doc_checksum',
        'extracted_data': {'fund_name': 'Test Fund'},
        'tables': []
    }


@pytest.mark.slow
@pytest.mark.performance
def test_chunking_performance_large_document(
    chunk_orchestrator,
    large_document,
    benchmark
):
    """Test chunking performance on large documents."""
    if pytest.config.pluginmanager.hasplugin('benchmark'):
        result = benchmark(chunk_orchestrator.create_chunks, large_document)
        assert len(result) > 0
    else:
        # Fallback if benchmark not available
        start_time = time.time()
        chunks = chunk_orchestrator.create_chunks(large_document)
        elapsed = time.time() - start_time

        assert len(chunks) > 0
        assert elapsed < 5.0  # Should complete in under 5 seconds
        print(f"Chunked {len(chunks)} chunks in {elapsed:.2f}s")


@pytest.mark.slow
@pytest.mark.performance
def test_token_counting_performance(chunk_orchestrator):
    """Test token counting performance."""
    # Generate large text
    large_text = "Word " * 50000  # ~200KB

    start_time = time.time()
    token_count = chunk_orchestrator.count_tokens(large_text)
    elapsed = time.time() - start_time

    assert token_count > 0
    assert elapsed < 1.0  # Should be fast (< 1 second for 200KB)
    print(f"Counted {token_count} tokens in {elapsed:.4f}s")


@pytest.mark.slow
@pytest.mark.performance
def test_chunk_creation_throughput(chunk_orchestrator):
    """Test chunk creation throughput."""
    # Create multiple small documents
    documents = [
        {
            'source_file': f'/path/to/doc_{i}.html',
            'file_type': 'html',
            'section': 'funds',
            'plain_text': "Test content. " * 500,
            'checksum': f'doc_{i}_checksum',
            'extracted_data': {},
            'tables': []
        }
        for i in range(100)
    ]

    start_time = time.time()
    total_chunks = 0

    for doc in documents:
        chunks = chunk_orchestrator.create_chunks(doc)
        total_chunks += len(chunks)

    elapsed = time.time() - start_time
    throughput = total_chunks / elapsed

    assert total_chunks > 0
    assert throughput > 10  # Should create at least 10 chunks/second
    print(f"Created {total_chunks} chunks in {elapsed:.2f}s ({throughput:.1f} chunks/s)")


@pytest.mark.slow
@pytest.mark.performance
def test_overlap_calculation_performance(chunk_orchestrator):
    """Test performance of overlap calculation."""
    large_chunks = ["Chunk text. " * 1000 for _ in range(100)]

    start_time = time.time()

    for _ in range(100):
        overlap_text = chunk_orchestrator._get_overlap_text(large_chunks, 300)
        assert len(overlap_text) > 0

    elapsed = time.time() - start_time

    assert elapsed < 1.0  # Should be very fast
    print(f"Calculated 100 overlaps in {elapsed:.4f}s")


@pytest.mark.slow
@pytest.mark.performance
def test_metadata_propagation_performance(chunk_orchestrator):
    """Test performance of metadata propagation."""
    document = {
        'source_file': '/path/to/doc.html',
        'file_type': 'html',
        'section': 'funds',
        'plain_text': "Content " * 5000,
        'checksum': 'meta_test',
        'extracted_data': {
            'fund_name': 'Test Fund',
            'nav_value': 100.50,
            'aum': '1000 crores',
            'risk_profile': 'moderate'
        },
        'tables': []
    }

    start_time = time.time()
    chunks = chunk_orchestrator.create_chunks(document)
    elapsed = time.time() - start_time

    # Verify metadata is in all chunks
    assert all('fund_name' in c.get('metadata', {}) for c in chunks)
    assert elapsed < 2.0
    print(f"Created {len(chunks)} chunks with metadata in {elapsed:.2f}s")


@pytest.mark.slow
@pytest.mark.performance
def test_database_operations_performance(chunk_orchestrator, tmp_path):
    """Test performance of SQLite diff database operations."""
    # Create many chunks
    chunks = [
        {
            'chunk_id': f'perf_chunk_{i}',
            'content': f'Content {i}',
            'metadata': {'parent_document_id': 'perf_doc', 'created_at': '2025-01-20'},
            'checksum': f'checksum_{i}'
        }
        for i in range(1000)
    ]

    start_time = time.time()

    # Test write performance
    for chunk in chunks:
        chunk_orchestrator.update_chunk_checksum(chunk, 1)

    write_elapsed = time.time() - start_time

    # Test read performance
    start_time = time.time()

    for chunk in chunks:
        status, version = chunk_orchestrator.check_chunk_diff(chunk)

    read_elapsed = time.time() - start_time

    assert write_elapsed < 5.0  # Should write 1000 in under 5s
    assert read_elapsed < 2.0   # Should read 1000 in under 2s

    print(f"SQLite: Wrote 1000 chunks in {write_elapsed:.2f}s, Read in {read_elapsed:.2f}s")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
