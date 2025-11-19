"""
End-to-end integration tests for BMF RAG Pipeline
"""
import pytest
import json
from pathlib import Path
from agents.parser.parser_agent import ParserAgent
from agents.chunk_orchestrator.chunk_agent import ChunkOrchestrator


@pytest.fixture
def pipeline_dirs(tmp_path):
    """Create directory structure for E2E test."""
    dirs = {
        'html_raw': tmp_path / "raw" / "html",
        'pdf_raw': tmp_path / "raw" / "pdf",
        'processed': tmp_path / "processed",
        'cache': tmp_path / "cache"
    }

    for dir_path in dirs.values():
        dir_path.mkdir(parents=True)

    return dirs


@pytest.fixture
def site_map(tmp_path):
    """Create site map for testing."""
    site_map_data = {
        "sections": {
            "funds": {
                "selectors": {
                    "fund_name": "h1.fund-title",
                    "nav": ".nav-value",
                    "aum": ".aum-value"
                }
            }
        }
    }

    site_map_path = tmp_path / "site_map.json"
    with open(site_map_path, 'w') as f:
        json.dump(site_map_data, f)

    return site_map_path


@pytest.fixture
def chunking_config(tmp_path):
    """Create chunking config for testing."""
    import yaml

    config = {
        "token_limits": {
            "max_tokens_per_chunk": 1200
        },
        "overlap": {
            "percentage": 25
        },
        "table_handling": {
            "preserve_verbatim": True
        }
    }

    config_path = tmp_path / "chunking.yml"
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

    return config_path


@pytest.fixture
def metadata_schema(tmp_path):
    """Create metadata schema for testing."""
    schema = {
        "required": ["chunk_id", "section"]
    }

    schema_path = tmp_path / "metadata_schema.json"
    with open(schema_path, 'w') as f:
        json.dump(schema, f)

    return schema_path


def test_parser_to_chunker_pipeline(pipeline_dirs, site_map, chunking_config, metadata_schema):
    """Test complete pipeline from HTML to chunks."""

    # Step 1: Create sample HTML file
    html_content = """
    <html>
        <body>
            <h1 class="fund-title">Bandhan Core Equity Fund</h1>
            <div class="nav-value">NAV: 45.23 (as of 2025-01-15)</div>
            <div class="aum-value">AUM: 5,234 crores</div>
            <div class="content">
                <p>The Bandhan Core Equity Fund is a diversified equity fund that primarily invests
                in large-cap stocks. The fund follows a growth-oriented investment strategy and
                benchmarks its performance against the Nifty 50 index.</p>

                <table>
                    <tr><th>Date</th><th>NAV</th><th>Return %</th></tr>
                    <tr><td>2025-01-15</td><td>45.23</td><td>18.5</td></tr>
                    <tr><td>2024-01-15</td><td>38.20</td><td>22.3</td></tr>
                    <tr><td>2023-01-15</td><td>31.30</td><td>15.8</td></tr>
                </table>

                <p>Risk Profile: Moderately High</p>
                <p>Minimum Investment: Rs. 5,000</p>
                <p>Fund Manager: John Doe</p>
            </div>
        </body>
    </html>
    """

    html_file = pipeline_dirs['html_raw'] / "funds" / "core_equity.html"
    html_file.parent.mkdir(parents=True, exist_ok=True)
    with open(html_file, 'w') as f:
        f.write(html_content)

    # Step 2: Parse HTML
    parser = ParserAgent(
        html_input_dir=str(pipeline_dirs['html_raw']),
        pdf_input_dir=str(pipeline_dirs['pdf_raw']),
        output_dir=str(pipeline_dirs['processed']),
        site_map_path=str(site_map)
    )

    parser_report = parser.run_parser(sections=['funds'])

    # Verify parser output
    assert parser_report['stats']['html_parsed'] > 0
    assert parser_report['stats']['failed_parses'] == 0

    # Check that JSON file was created
    parsed_json = pipeline_dirs['processed'] / "funds" / "core_equity.json"
    assert parsed_json.exists()

    with open(parsed_json, 'r') as f:
        parsed_data = json.load(f)

    assert parsed_data['file_type'] == 'html'
    assert parsed_data['section'] == 'funds'
    assert 'Bandhan Core Equity Fund' in parsed_data['plain_text']

    # Step 3: Create chunks
    orchestrator = ChunkOrchestrator(
        input_dir=str(pipeline_dirs['processed']),
        chunking_config_path=str(chunking_config),
        metadata_schema_path=str(metadata_schema),
        diff_db_path=str(pipeline_dirs['cache'] / "diff.db")
    )

    chunk_report = orchestrator.run_orchestrator(sections=['funds'])

    # Verify chunking output
    assert chunk_report['stats']['total_documents'] > 0
    assert chunk_report['stats']['total_chunks'] > 0
    assert chunk_report['stats']['new_chunks'] > 0

    # Step 4: Verify chunks have correct structure
    # Re-process to check chunk metadata
    with open(parsed_json, 'r') as f:
        document = json.load(f)

    chunks = orchestrator.create_chunks(document)

    assert len(chunks) > 0

    for chunk in chunks:
        # Verify chunk structure
        assert 'chunk_id' in chunk
        assert 'content' in chunk
        assert 'metadata' in chunk
        assert 'checksum' in chunk
        assert 'token_count' in chunk

        # Verify metadata
        metadata = chunk['metadata']
        assert metadata['section'] == 'funds'
        assert metadata['file_type'] == 'html'

    # Step 5: Verify table chunks
    table_chunks = [c for c in chunks if c['metadata'].get('has_table')]

    if parsed_data.get('table_count', 0) > 0:
        assert len(table_chunks) > 0


def test_incremental_update_detection(pipeline_dirs, site_map, chunking_config, metadata_schema):
    """Test that chunker detects updates vs new content."""

    # Create initial HTML
    html_content_v1 = "<html><body><p>Initial content for funds page.</p></body></html>"
    html_file = pipeline_dirs['html_raw'] / "funds" / "test_fund.html"
    html_file.parent.mkdir(parents=True, exist_ok=True)

    with open(html_file, 'w') as f:
        f.write(html_content_v1)

    # First run: Parse and chunk
    parser = ParserAgent(
        html_input_dir=str(pipeline_dirs['html_raw']),
        pdf_input_dir=str(pipeline_dirs['pdf_raw']),
        output_dir=str(pipeline_dirs['processed']),
        site_map_path=str(site_map)
    )
    parser.run_parser(sections=['funds'])

    orchestrator = ChunkOrchestrator(
        input_dir=str(pipeline_dirs['processed']),
        chunking_config_path=str(chunking_config),
        metadata_schema_path=str(metadata_schema),
        diff_db_path=str(pipeline_dirs['cache'] / "diff.db")
    )

    report1 = orchestrator.run_orchestrator(sections=['funds'])

    # All chunks should be new
    assert report1['stats']['new_chunks'] > 0
    assert report1['stats']['unchanged_chunks'] == 0

    # Second run: Same content
    orchestrator2 = ChunkOrchestrator(
        input_dir=str(pipeline_dirs['processed']),
        chunking_config_path=str(chunking_config),
        metadata_schema_path=str(metadata_schema),
        diff_db_path=str(pipeline_dirs['cache'] / "diff.db")
    )

    report2 = orchestrator2.run_orchestrator(sections=['funds'])

    # All chunks should be unchanged
    assert report2['stats']['unchanged_chunks'] > 0
    assert report2['stats']['new_chunks'] == 0

    # Third run: Updated content
    html_content_v2 = "<html><body><p>UPDATED content for funds page with more information.</p></body></html>"
    with open(html_file, 'w') as f:
        f.write(html_content_v2)

    parser.run_parser(sections=['funds'])

    orchestrator3 = ChunkOrchestrator(
        input_dir=str(pipeline_dirs['processed']),
        chunking_config_path=str(chunking_config),
        metadata_schema_path=str(metadata_schema),
        diff_db_path=str(pipeline_dirs['cache'] / "diff.db")
    )

    report3 = orchestrator3.run_orchestrator(sections=['funds'])

    # Some chunks should be updated
    assert report3['stats']['updated_chunks'] > 0 or report3['stats']['new_chunks'] > 0


def test_stats_aggregation(pipeline_dirs, site_map, chunking_config, metadata_schema):
    """Test that pipeline stats are correctly aggregated."""

    # Create multiple HTML files
    for i in range(3):
        html_content = f"<html><body><p>Content for fund {i}. This is test data.</p></body></html>"
        html_file = pipeline_dirs['html_raw'] / "funds" / f"fund{i}.html"
        html_file.parent.mkdir(parents=True, exist_ok=True)
        with open(html_file, 'w') as f:
            f.write(html_content)

    # Parse all files
    parser = ParserAgent(
        html_input_dir=str(pipeline_dirs['html_raw']),
        pdf_input_dir=str(pipeline_dirs['pdf_raw']),
        output_dir=str(pipeline_dirs['processed']),
        site_map_path=str(site_map)
    )

    parser_report = parser.run_parser(sections=['funds'])

    # Verify parser stats
    assert parser_report['stats']['total_files'] == 3
    assert parser_report['stats']['html_parsed'] == 3

    # Chunk all files
    orchestrator = ChunkOrchestrator(
        input_dir=str(pipeline_dirs['processed']),
        chunking_config_path=str(chunking_config),
        metadata_schema_path=str(metadata_schema),
        diff_db_path=str(pipeline_dirs['cache'] / "diff.db")
    )

    chunk_report = orchestrator.run_orchestrator(sections=['funds'])

    # Verify chunking stats
    assert chunk_report['stats']['total_documents'] == 3
    assert chunk_report['stats']['total_chunks'] >= 3  # At least one chunk per document


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
