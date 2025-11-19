"""
Unit tests for Parser Agent
"""
import pytest
import json
from pathlib import Path
from agents.parser.parser_agent import ParserAgent


@pytest.fixture
def parser_agent(tmp_path):
    """Create a ParserAgent instance with temporary directories."""
    html_dir = tmp_path / "html"
    pdf_dir = tmp_path / "pdf"
    output_dir = tmp_path / "output"

    html_dir.mkdir()
    pdf_dir.mkdir()
    output_dir.mkdir()

    # Create a minimal site map
    site_map = {
        "sections": {
            "test_section": {
                "selectors": {
                    "title": "h1",
                    "content": ".main-content"
                }
            }
        }
    }

    site_map_path = tmp_path / "site_map.json"
    with open(site_map_path, 'w') as f:
        json.dump(site_map, f)

    return ParserAgent(
        html_input_dir=str(html_dir),
        pdf_input_dir=str(pdf_dir),
        output_dir=str(output_dir),
        site_map_path=str(site_map_path)
    )


def test_parser_agent_initialization(parser_agent):
    """Test that Parser Agent initializes correctly."""
    assert parser_agent is not None
    assert parser_agent.site_map is not None
    assert 'test_section' in parser_agent.site_map['sections']


def test_parse_html_creates_output(parser_agent, tmp_path):
    """Test that parsing HTML creates output files."""
    # Create a sample HTML file
    html_content = """
    <html>
        <body>
            <h1>Test Fund</h1>
            <div class="main-content">
                <p>This is a test fund with sample content.</p>
                <table>
                    <tr><th>NAV</th><td>100.50</td></tr>
                    <tr><th>AUM</th><td>1000 crores</td></tr>
                </table>
            </div>
        </body>
    </html>
    """

    html_file = parser_agent.html_input_dir / "test_section" / "test.html"
    html_file.parent.mkdir(parents=True, exist_ok=True)
    with open(html_file, 'w') as f:
        f.write(html_content)

    # Parse the HTML
    result = parser_agent.parse_html(html_file, "test_section")

    # Check result
    assert result is not None
    assert result['file_type'] == 'html'
    assert result['section'] == 'test_section'
    assert len(result.get('plain_text', '')) > 0

    # Check that output files were created
    output_json = parser_agent.output_dir / "test_section" / "test.json"
    output_md = parser_agent.output_dir / "test_section" / "test.md"

    assert output_json.exists()
    assert output_md.exists()


def test_parse_html_extracts_tables(parser_agent, tmp_path):
    """Test that parser correctly extracts tables from HTML."""
    html_content = """
    <html>
        <body>
            <table>
                <tr><th>Date</th><th>NAV</th></tr>
                <tr><td>2025-01-15</td><td>100.50</td></tr>
                <tr><td>2025-01-16</td><td>101.25</td></tr>
            </table>
        </body>
    </html>
    """

    html_file = parser_agent.html_input_dir / "test_section" / "table_test.html"
    html_file.parent.mkdir(parents=True, exist_ok=True)
    with open(html_file, 'w') as f:
        f.write(html_content)

    result = parser_agent.parse_html(html_file, "test_section")

    # Check tables were extracted
    assert 'tables' in result
    assert len(result['tables']) > 0
    assert result['table_count'] > 0

    # Check table structure
    table = result['tables'][0]
    assert 'markdown' in table
    assert 'json' in table
    assert table['rows'] == 2  # Excluding header


def test_parse_html_handles_errors(parser_agent):
    """Test that parser handles missing files gracefully."""
    non_existent_file = parser_agent.html_input_dir / "test_section" / "missing.html"

    result = parser_agent.parse_html(non_existent_file, "test_section")

    assert 'error' in result
    assert parser_agent.stats['failed_parses'] > 0


def test_stats_tracking(parser_agent, tmp_path):
    """Test that stats are correctly tracked."""
    # Create sample HTML files
    for i in range(3):
        html_content = f"<html><body><p>Test content {i}</p></body></html>"
        html_file = parser_agent.html_input_dir / "test_section" / f"test{i}.html"
        html_file.parent.mkdir(parents=True, exist_ok=True)
        with open(html_file, 'w') as f:
            f.write(html_content)

    # Parse section
    parser_agent.parse_section("test_section")

    # Check stats
    assert parser_agent.stats['total_files'] == 3
    assert parser_agent.stats['html_parsed'] == 3
    assert parser_agent.stats['failed_parses'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
