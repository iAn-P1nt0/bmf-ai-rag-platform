"""
Document Harvester - Downloads PDFs/KIMs/factsheets, verifies checksums.
Schedule: Daily 02:30 IST
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
import boto3
import requests
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import urljoin
import mimetypes


class DocumentHarvester:
    """Agent responsible for harvesting PDF and document files."""

    def __init__(
        self,
        site_map_path: str,
        html_dir: str = "./data/raw/html",
        output_dir: str = "./data/raw/pdf",
        s3_bucket: Optional[str] = None
    ):
        """
        Initialize Document Harvester.

        Args:
            site_map_path: Path to SITE_MAP.json
            html_dir: Directory containing scraped HTML files
            output_dir: Local directory for downloaded documents
            s3_bucket: S3 bucket for document storage
        """
        self.site_map_path = Path(site_map_path)
        self.html_dir = Path(html_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.s3_bucket = s3_bucket
        self.s3_client = boto3.client('s3') if s3_bucket else None
        self.site_map = self._load_site_map()
        self.checksums_db = self._load_checksums_db()
        self.stats = {
            'total_documents': 0,
            'new_documents': 0,
            'updated_documents': 0,
            'skipped_documents': 0,
            'failed_downloads': 0
        }

    def _load_site_map(self) -> Dict:
        """Load SITE_MAP configuration."""
        with open(self.site_map_path, 'r') as f:
            return json.load(f)

    def _load_checksums_db(self) -> Dict[str, str]:
        """Load checksums database for deduplication."""
        checksums_path = self.output_dir / "checksums.json"
        if checksums_path.exists():
            with open(checksums_path, 'r') as f:
                return json.load(f)
        return {}

    def _save_checksums_db(self):
        """Save checksums database."""
        checksums_path = self.output_dir / "checksums.json"
        with open(checksums_path, 'w') as f:
            json.dump(self.checksums_db, f, indent=2)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def extract_document_links(self, html_content: str, base_url: str, file_types: List[str]) -> List[Dict]:
        """
        Extract document links from HTML content.

        Args:
            html_content: HTML content to parse
            base_url: Base URL for resolving relative links
            file_types: List of file extensions to extract (e.g., ['pdf', 'xlsx'])

        Returns:
            List of document metadata dictionaries
        """
        soup = BeautifulSoup(html_content, 'lxml')
        documents = []

        # Find all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(base_url, href)

            # Check if link points to a document
            for file_type in file_types:
                if full_url.lower().endswith(f'.{file_type}'):
                    # Try to extract document metadata
                    link_text = link.get_text(strip=True)
                    parent_text = link.parent.get_text(strip=True) if link.parent else ""

                    documents.append({
                        'url': full_url,
                        'file_type': file_type,
                        'link_text': link_text,
                        'context': parent_text,
                        'source_url': base_url
                    })
                    break

        return documents

    def classify_document(self, doc_info: Dict, patterns: Dict[str, str]) -> Optional[str]:
        """
        Classify document type based on URL patterns.

        Args:
            doc_info: Document information dictionary
            patterns: Document type patterns from SITE_MAP

        Returns:
            Document type or None
        """
        import re

        url = doc_info['url'].lower()
        link_text = doc_info['link_text'].lower()

        for doc_type, pattern in patterns.items():
            if re.search(pattern, url) or re.search(pattern, link_text):
                return doc_type

        return 'other'

    async def download_document(self, url: str, output_path: Path) -> bool:
        """
        Download document from URL.

        Args:
            url: Document URL
            output_path: Local path to save document

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Downloading: {url}")

            response = requests.get(
                url,
                timeout=60,
                stream=True,
                headers={
                    'User-Agent': self.site_map['global_settings']['user_agent']
                }
            )

            if response.status_code == 200:
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                logger.info(f"Downloaded successfully: {output_path.name}")
                return True
            else:
                logger.error(f"Failed to download {url}: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False

    def harvest_section(self, section_name: str) -> List[Dict]:
        """
        Harvest documents from a section.

        Args:
            section_name: Name of section from SITE_MAP

        Returns:
            List of harvested document metadata
        """
        section_config = self.site_map['sections'].get(section_name)
        if not section_config:
            logger.error(f"Section '{section_name}' not found in SITE_MAP")
            return []

        file_types = section_config.get('file_types', [])
        patterns = section_config.get('patterns', {})

        if not file_types:
            logger.info(f"No file types configured for section '{section_name}', skipping")
            return []

        logger.info(f"Harvesting documents from section '{section_name}'")

        # Read scraped HTML files for this section
        section_html_dir = self.html_dir / section_name
        if not section_html_dir.exists():
            logger.warning(f"No HTML files found for section '{section_name}'")
            return []

        all_documents = []
        harvested = []

        # Extract document links from HTML files
        for html_file in section_html_dir.glob("*.html"):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                # Extract base URL from metadata (you'd track this during scraping)
                # For now, use section URL patterns
                base_url = section_config['url_patterns'][0].replace('*', '')

                documents = self.extract_document_links(html_content, base_url, file_types)
                all_documents.extend(documents)

            except Exception as e:
                logger.error(f"Error processing {html_file}: {e}")

        logger.info(f"Found {len(all_documents)} documents in section '{section_name}'")

        # Download and process documents
        for doc_info in all_documents:
            self.stats['total_documents'] += 1

            # Classify document
            doc_type = self.classify_document(doc_info, patterns)

            # Generate filename
            url_hash = hashlib.md5(doc_info['url'].encode()).hexdigest()
            filename = f"{doc_type}_{url_hash}.{doc_info['file_type']}"
            output_path = self.output_dir / section_name / filename

            # Check if already downloaded
            if doc_info['url'] in self.checksums_db:
                logger.debug(f"Document already exists: {filename}")
                self.stats['skipped_documents'] += 1
                continue

            # Download document
            import asyncio
            success = asyncio.run(self.download_document(doc_info['url'], output_path))

            if success:
                # Calculate checksum
                checksum = self._calculate_checksum(output_path)

                # Check for updates
                if doc_info['url'] in self.checksums_db:
                    if self.checksums_db[doc_info['url']] != checksum:
                        self.stats['updated_documents'] += 1
                        logger.info(f"Document updated: {filename}")
                else:
                    self.stats['new_documents'] += 1

                # Update checksums DB
                self.checksums_db[doc_info['url']] = checksum

                # Upload to S3 if configured
                s3_key = None
                if self.s3_client and self.s3_bucket:
                    s3_key = f"raw-pdf/{datetime.now().strftime('%Y-%m-%d')}/{section_name}/{filename}"
                    with open(output_path, 'rb') as f:
                        self.s3_client.put_object(
                            Bucket=self.s3_bucket,
                            Key=s3_key,
                            Body=f.read(),
                            Metadata={
                                'url': doc_info['url'],
                                'doc_type': doc_type,
                                'section': section_name
                            }
                        )

                # Create metadata
                metadata = {
                    'url': doc_info['url'],
                    'file_type': doc_info['file_type'],
                    'doc_type': doc_type,
                    'filename': filename,
                    'local_path': str(output_path),
                    's3_key': s3_key,
                    'checksum': checksum,
                    'downloaded_at': datetime.now(timezone.utc).isoformat(),
                    'link_text': doc_info['link_text'],
                    'section': section_name
                }

                harvested.append(metadata)

            else:
                self.stats['failed_downloads'] += 1

        # Save checksums DB
        self._save_checksums_db()

        return harvested

    def harvest_all_sections(self, sections: Optional[List[str]] = None) -> Dict:
        """
        Harvest documents from all sections.

        Args:
            sections: Optional list of section names

        Returns:
            Harvest report
        """
        logger.info("Starting Document Harvester run...")

        if sections is None:
            sections = [
                name for name, config in self.site_map['sections'].items()
                if config.get('file_types')
            ]

        all_harvested = {}

        for section in sections:
            harvested = self.harvest_section(section)
            all_harvested[section] = harvested

        # Generate report
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sections_harvested': len(sections),
            'stats': self.stats,
            'harvested': all_harvested
        }

        # Save report
        report_path = self.output_dir / f"harvest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info("Document Harvester run completed")
        logger.info(f"Stats: {json.dumps(self.stats, indent=2)}")
        logger.info(f"Report saved to {report_path}")

        return report


def main():
    """Main entry point for Document Harvester."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    site_map_path = os.getenv('SITE_MAP_CONFIG_PATH', './configs/site_map/SITE_MAP.json')
    html_dir = os.getenv('SCRAPER_OUTPUT_DIR', './data/raw/html')
    output_dir = os.getenv('HARVESTER_OUTPUT_DIR', './data/raw/pdf')
    s3_bucket = os.getenv('S3_BUCKET_RAW')

    harvester = DocumentHarvester(
        site_map_path=site_map_path,
        html_dir=html_dir,
        output_dir=output_dir,
        s3_bucket=s3_bucket
    )

    report = harvester.harvest_all_sections()

    logger.info(f"Harvesting completed: {report['stats']}")


if __name__ == "__main__":
    main()
