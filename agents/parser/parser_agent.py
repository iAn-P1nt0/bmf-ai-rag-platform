"""
Parser Agent - Converts HTML/PDF to structured Markdown/JSON.
Schedule: Daily 03:00 IST (follows scraping completion)

Implements AGENTS.md Section 2 requirements:
- Run Unstructured.io + custom table preservers
- Convert HTML/PDF into Markdown + JSON (tables, metrics)
- Apply semantic tagging (fund, risk, doc_type)
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from bs4 import BeautifulSoup
from loguru import logger
import pandas as pd
import boto3

try:
    from unstructured.partition.html import partition_html
    from unstructured.partition.pdf import partition_pdf
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    logger.warning("Unstructured.io not installed. Install with: pip install unstructured[pdf]")
    UNSTRUCTURED_AVAILABLE = False


class ParserAgent:
    """Agent responsible for parsing HTML and PDF documents into structured format."""

    def __init__(
        self,
        html_input_dir: str = "./data/raw/html",
        pdf_input_dir: str = "./data/raw/pdf",
        output_dir: str = "./data/processed",
        site_map_path: str = "./configs/site_map/SITE_MAP.json",
        s3_bucket: Optional[str] = None
    ):
        """
        Initialize Parser Agent.

        Args:
            html_input_dir: Directory containing raw HTML files
            pdf_input_dir: Directory containing raw PDF files
            output_dir: Directory for parsed Markdown/JSON output
            site_map_path: Path to SITE_MAP.json for section metadata
            s3_bucket: S3 bucket for processed data storage
        """
        self.html_input_dir = Path(html_input_dir)
        self.pdf_input_dir = Path(pdf_input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.site_map_path = Path(site_map_path)
        self.s3_bucket = s3_bucket
        self.s3_client = boto3.client('s3') if s3_bucket else None
        self.site_map = self._load_site_map()
        self.stats = {
            'total_files': 0,
            'html_parsed': 0,
            'pdf_parsed': 0,
            'tables_extracted': 0,
            'failed_parses': 0
        }

    def _load_site_map(self) -> Dict:
        """Load SITE_MAP configuration for metadata."""
        with open(self.site_map_path, 'r') as f:
            return json.load(f)

    def parse_html(self, html_file: Path, section: str) -> Dict:
        """
        Parse HTML to structured Markdown with preserved tables.

        Args:
            html_file: Path to HTML file
            section: Section name from SITE_MAP

        Returns:
            Parsed content with metadata
        """
        logger.info(f"Parsing HTML: {html_file.name}")

        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Parse with Beautiful Soup for custom extraction
            soup = BeautifulSoup(html_content, 'lxml')

            # Extract metadata using section selectors
            section_config = self.site_map['sections'].get(section, {})
            selectors = section_config.get('selectors', {})

            extracted_data = {}
            for key, selector in selectors.items():
                try:
                    element = soup.select_one(selector)
                    if element:
                        extracted_data[key] = element.get_text(strip=True)
                except Exception as e:
                    logger.debug(f"Could not extract {key}: {e}")

            # Extract tables
            tables = []
            for idx, table in enumerate(soup.find_all('table')):
                try:
                    # Convert to pandas DataFrame
                    df = pd.read_html(str(table))[0]

                    # Convert to markdown
                    markdown_table = df.to_markdown(index=False)

                    # Also keep as JSON
                    table_json = df.to_dict('records')

                    tables.append({
                        'index': idx,
                        'markdown': markdown_table,
                        'json': table_json,
                        'rows': len(df),
                        'columns': len(df.columns)
                    })

                    self.stats['tables_extracted'] += 1
                except Exception as e:
                    logger.warning(f"Failed to parse table {idx}: {e}")

            # Use Unstructured.io if available for semantic extraction
            semantic_elements = []
            if UNSTRUCTURED_AVAILABLE:
                try:
                    elements = partition_html(text=html_content)
                    semantic_elements = [
                        {
                            'type': str(type(elem).__name__),
                            'text': str(elem),
                            'metadata': elem.metadata.to_dict() if hasattr(elem, 'metadata') else {}
                        }
                        for elem in elements
                    ]
                except Exception as e:
                    logger.warning(f"Unstructured.io parsing failed: {e}")

            # Extract plain text
            plain_text = soup.get_text(separator='\n', strip=True)

            # Build structured output
            parsed = {
                'source_file': str(html_file),
                'section': section,
                'parsed_at': datetime.now(timezone.utc).isoformat(),
                'file_type': 'html',
                'extracted_data': extracted_data,
                'tables': tables,
                'table_count': len(tables),
                'semantic_elements': semantic_elements,
                'element_count': len(semantic_elements),
                'plain_text': plain_text,
                'text_length': len(plain_text),
                'checksum': hashlib.sha256(html_content.encode()).hexdigest()
            }

            # Save as JSON
            output_file = self.output_dir / section / f"{html_file.stem}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)

            # Save markdown version
            markdown = self._create_markdown(parsed)
            markdown_file = self.output_dir / section / f"{html_file.stem}.md"
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown)

            # Upload to S3 if configured
            if self.s3_client and self.s3_bucket:
                s3_key = f"processed/{datetime.now().strftime('%Y-%m-%d')}/{section}/{html_file.stem}.json"
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=json.dumps(parsed, ensure_ascii=False).encode('utf-8'),
                    ContentType='application/json'
                )
                parsed['s3_key'] = s3_key

            self.stats['html_parsed'] += 1
            logger.info(f"Parsed HTML: {html_file.name} -> {output_file.name}")

            return parsed

        except Exception as e:
            logger.error(f"Failed to parse HTML {html_file}: {e}")
            self.stats['failed_parses'] += 1
            return {'error': str(e), 'source_file': str(html_file)}

    def parse_pdf(self, pdf_file: Path, section: str) -> Dict:
        """
        Parse PDF to structured format with table preservation.

        Args:
            pdf_file: Path to PDF file
            section: Section name from SITE_MAP

        Returns:
            Parsed content with metadata
        """
        logger.info(f"Parsing PDF: {pdf_file.name}")

        try:
            # Use Unstructured.io for PDF parsing
            if not UNSTRUCTURED_AVAILABLE:
                logger.warning("Unstructured.io required for PDF parsing")
                return {'error': 'unstructured_not_available', 'source_file': str(pdf_file)}

            # Partition PDF
            elements = partition_pdf(
                filename=str(pdf_file),
                strategy="hi_res",  # High-resolution for better table extraction
                infer_table_structure=True,
                include_page_breaks=True
            )

            # Process elements
            pages = {}
            tables = []
            current_page = 1

            for elem in elements:
                elem_type = type(elem).__name__
                elem_text = str(elem)
                elem_metadata = elem.metadata.to_dict() if hasattr(elem, 'metadata') else {}

                # Track page number
                if 'page_number' in elem_metadata:
                    current_page = elem_metadata['page_number']

                if current_page not in pages:
                    pages[current_page] = {
                        'page_number': current_page,
                        'elements': []
                    }

                pages[current_page]['elements'].append({
                    'type': elem_type,
                    'text': elem_text,
                    'metadata': elem_metadata
                })

                # Extract tables
                if elem_type == 'Table':
                    try:
                        # Parse table from text
                        # Unstructured.io provides tables as text, we convert to structured format
                        tables.append({
                            'page': current_page,
                            'text': elem_text,
                            'type': 'table'
                        })
                        self.stats['tables_extracted'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to process table on page {current_page}: {e}")

            # Combine all text
            plain_text = '\n'.join(str(elem) for elem in elements)

            # Build structured output
            parsed = {
                'source_file': str(pdf_file),
                'section': section,
                'parsed_at': datetime.now(timezone.utc).isoformat(),
                'file_type': 'pdf',
                'page_count': len(pages),
                'pages': list(pages.values()),
                'tables': tables,
                'table_count': len(tables),
                'element_count': len(elements),
                'plain_text': plain_text,
                'text_length': len(plain_text),
                'checksum': hashlib.sha256(pdf_file.read_bytes()).hexdigest()
            }

            # Save as JSON
            output_file = self.output_dir / section / f"{pdf_file.stem}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)

            # Save markdown version
            markdown = self._create_markdown_from_pdf(parsed)
            markdown_file = self.output_dir / section / f"{pdf_file.stem}.md"
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown)

            # Upload to S3 if configured
            if self.s3_client and self.s3_bucket:
                s3_key = f"processed/{datetime.now().strftime('%Y-%m-%d')}/{section}/{pdf_file.stem}.json"
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=json.dumps(parsed, ensure_ascii=False).encode('utf-8'),
                    ContentType='application/json'
                )
                parsed['s3_key'] = s3_key

            self.stats['pdf_parsed'] += 1
            logger.info(f"Parsed PDF: {pdf_file.name} -> {output_file.name}")

            return parsed

        except Exception as e:
            logger.error(f"Failed to parse PDF {pdf_file}: {e}")
            self.stats['failed_parses'] += 1
            return {'error': str(e), 'source_file': str(pdf_file)}

    def _create_markdown(self, parsed: Dict) -> str:
        """Create markdown representation of parsed HTML."""
        md_parts = [f"# {parsed.get('section', 'Document').title()}\n"]

        # Add extracted data
        if parsed.get('extracted_data'):
            md_parts.append("## Extracted Data\n")
            for key, value in parsed['extracted_data'].items():
                md_parts.append(f"**{key.replace('_', ' ').title()}**: {value}\n")
            md_parts.append("\n")

        # Add tables
        if parsed.get('tables'):
            md_parts.append("## Tables\n")
            for table in parsed['tables']:
                md_parts.append(f"\n### Table {table['index'] + 1}\n")
                md_parts.append(table['markdown'])
                md_parts.append("\n")

        # Add plain text
        if parsed.get('plain_text'):
            md_parts.append("\n## Content\n")
            md_parts.append(parsed['plain_text'])

        return '\n'.join(md_parts)

    def _create_markdown_from_pdf(self, parsed: Dict) -> str:
        """Create markdown representation of parsed PDF."""
        md_parts = [f"# {parsed.get('section', 'Document').title()} - {Path(parsed['source_file']).stem}\n"]

        # Add page-by-page content
        for page in parsed.get('pages', []):
            md_parts.append(f"\n## Page {page['page_number']}\n")
            for elem in page['elements']:
                if elem['type'] == 'Title':
                    md_parts.append(f"\n### {elem['text']}\n")
                elif elem['type'] == 'Table':
                    md_parts.append(f"\n**Table:**\n```\n{elem['text']}\n```\n")
                else:
                    md_parts.append(f"{elem['text']}\n")

        return '\n'.join(md_parts)

    def parse_section(self, section: str) -> List[Dict]:
        """
        Parse all files in a section.

        Args:
            section: Section name from SITE_MAP

        Returns:
            List of parsed documents
        """
        logger.info(f"Parsing section: {section}")

        parsed_docs = []

        # Parse HTML files
        html_section_dir = self.html_input_dir / section
        if html_section_dir.exists():
            for html_file in html_section_dir.glob("*.html"):
                self.stats['total_files'] += 1
                parsed = self.parse_html(html_file, section)
                parsed_docs.append(parsed)

        # Parse PDF files
        pdf_section_dir = self.pdf_input_dir / section
        if pdf_section_dir.exists():
            for pdf_file in pdf_section_dir.glob("*.pdf"):
                self.stats['total_files'] += 1
                parsed = self.parse_pdf(pdf_file, section)
                parsed_docs.append(parsed)

        logger.info(f"Parsed {len(parsed_docs)} documents in section '{section}'")

        return parsed_docs

    def run_parser(self, sections: Optional[List[str]] = None) -> Dict:
        """
        Execute parser on all sections.

        Args:
            sections: Optional list of sections to parse

        Returns:
            Parser report
        """
        logger.info("Starting Parser Agent run...")

        if sections is None:
            sections = list(self.site_map['sections'].keys())

        all_parsed = {}

        for section in sections:
            parsed_docs = self.parse_section(section)
            all_parsed[section] = parsed_docs

        # Generate report
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sections_parsed': len(sections),
            'stats': self.stats,
            'parsed_documents': all_parsed
        }

        # Save report
        report_path = self.output_dir / f"parser_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            # Don't include full parsed documents in report (too large)
            report_summary = {
                'timestamp': report['timestamp'],
                'sections_parsed': report['sections_parsed'],
                'stats': report['stats'],
                'document_count_by_section': {
                    section: len(docs) for section, docs in all_parsed.items()
                }
            }
            json.dump(report_summary, f, indent=2)

        logger.info("Parser Agent run completed")
        logger.info(f"Stats: {json.dumps(self.stats, indent=2)}")
        logger.info(f"Report saved to {report_path}")

        return report


def main():
    """Main entry point for Parser Agent."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    site_map_path = os.getenv('SITE_MAP_CONFIG_PATH', './configs/site_map/SITE_MAP.json')
    html_input_dir = os.getenv('SCRAPER_OUTPUT_DIR', './data/raw/html')
    pdf_input_dir = os.getenv('HARVESTER_OUTPUT_DIR', './data/raw/pdf')
    output_dir = os.getenv('PARSER_OUTPUT_DIR', './data/processed')
    s3_bucket = os.getenv('S3_BUCKET_PROCESSED')

    agent = ParserAgent(
        html_input_dir=html_input_dir,
        pdf_input_dir=pdf_input_dir,
        output_dir=output_dir,
        site_map_path=site_map_path,
        s3_bucket=s3_bucket
    )

    report = agent.run_parser()

    logger.info(f"Parsing completed: {report['stats']}")


if __name__ == "__main__":
    main()
