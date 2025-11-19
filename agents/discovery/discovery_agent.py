"""
Discovery Agent - Maintains SITE_MAP manifest and detects new/changed URLs.
Schedule: Daily 00:30 IST
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from loguru import logger
import xml.etree.ElementTree as ET


class DiscoveryAgent:
    """Agent responsible for discovering and tracking site structure changes."""

    def __init__(self, config_path: str, output_path: str = None):
        """
        Initialize Discovery Agent.

        Args:
            config_path: Path to SITE_MAP.json
            output_path: Path to save updated SITE_MAP.json
        """
        self.config_path = Path(config_path)
        self.output_path = Path(output_path) if output_path else self.config_path
        self.site_map = self._load_site_map()
        self.discovered_urls: Dict[str, Set[str]] = {section: set() for section in self.site_map['sections'].keys()}
        self.changes: Dict[str, List[str]] = {
            'new_urls': [],
            'removed_urls': [],
            'modified_sections': []
        }

    def _load_site_map(self) -> Dict:
        """Load existing SITE_MAP.json configuration."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"SITE_MAP not found at {self.config_path}")
            raise

    def _save_site_map(self):
        """Save updated SITE_MAP.json with version control."""
        self.site_map['last_updated'] = datetime.now(timezone.utc).isoformat()

        # Create backup
        backup_path = self.output_path.parent / f"SITE_MAP_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if self.output_path.exists():
            with open(self.output_path, 'r') as f:
                backup_data = json.load(f)
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)

        # Save updated version
        with open(self.output_path, 'w') as f:
            json.dump(self.site_map, f, indent=2)

        logger.info(f"Updated SITE_MAP saved to {self.output_path}")
        logger.info(f"Backup created at {backup_path}")

    def fetch_sitemap_xml(self, base_url: str) -> List[str]:
        """
        Fetch and parse sitemap.xml for URLs.

        Args:
            base_url: Base URL of the website

        Returns:
            List of discovered URLs
        """
        sitemap_urls = [
            urljoin(base_url, '/sitemap.xml'),
            urljoin(base_url, '/sitemap_index.xml'),
            urljoin(base_url, '/robots.txt')
        ]

        discovered = []

        for sitemap_url in sitemap_urls:
            try:
                response = requests.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    if 'sitemap.xml' in sitemap_url or 'sitemap_index.xml' in sitemap_url:
                        discovered.extend(self._parse_sitemap_xml(response.content))
                    elif 'robots.txt' in sitemap_url:
                        discovered.extend(self._parse_robots_txt(response.text))

                    logger.info(f"Fetched {sitemap_url}: {len(discovered)} URLs found")
            except Exception as e:
                logger.warning(f"Failed to fetch {sitemap_url}: {e}")

        return discovered

    def _parse_sitemap_xml(self, xml_content: bytes) -> List[str]:
        """Parse sitemap XML and extract URLs."""
        urls = []
        try:
            root = ET.fromstring(xml_content)
            # Handle both sitemap and sitemap index formats
            for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                urls.append(url_elem.text)
        except Exception as e:
            logger.error(f"Error parsing sitemap XML: {e}")
        return urls

    def _parse_robots_txt(self, robots_content: str) -> List[str]:
        """Extract sitemap URLs from robots.txt."""
        urls = []
        for line in robots_content.split('\n'):
            if line.lower().startswith('sitemap:'):
                sitemap_url = line.split(':', 1)[1].strip()
                urls.append(sitemap_url)
        return urls

    def discover_urls_by_crawl(self, base_url: str, section_patterns: List[str], max_depth: int = 3) -> Set[str]:
        """
        Discover URLs by crawling pages matching section patterns.

        Args:
            base_url: Base URL to start crawling
            section_patterns: URL patterns to match
            max_depth: Maximum crawl depth

        Returns:
            Set of discovered URLs
        """
        discovered = set()
        visited = set()
        to_visit = [(base_url, 0)]

        while to_visit:
            url, depth = to_visit.pop(0)

            if url in visited or depth > max_depth:
                continue

            try:
                response = requests.get(url, timeout=10, headers={
                    'User-Agent': self.site_map['global_settings']['user_agent']
                })

                if response.status_code == 200:
                    visited.add(url)
                    soup = BeautifulSoup(response.content, 'lxml')

                    # Extract all links
                    for link in soup.find_all('a', href=True):
                        full_url = urljoin(url, link['href'])

                        # Check if URL matches any section pattern
                        if self._matches_patterns(full_url, section_patterns):
                            discovered.add(full_url)
                            if depth < max_depth:
                                to_visit.append((full_url, depth + 1))

                logger.debug(f"Crawled {url}: found {len(discovered)} matching URLs")

            except Exception as e:
                logger.warning(f"Failed to crawl {url}: {e}")

        return discovered

    def _matches_patterns(self, url: str, patterns: List[str]) -> bool:
        """Check if URL matches any of the given patterns."""
        import re
        for pattern in patterns:
            # Convert glob-style pattern to regex
            regex_pattern = pattern.replace('*', '.*')
            if re.match(regex_pattern, url):
                return True
        return False

    def detect_changes(self, section: str, current_urls: Set[str], previous_urls: Set[str]) -> Dict[str, Set[str]]:
        """
        Detect new, removed, and modified URLs for a section.

        Args:
            section: Section name
            current_urls: Currently discovered URLs
            previous_urls: Previously known URLs

        Returns:
            Dictionary with 'new', 'removed', 'unchanged' sets
        """
        return {
            'new': current_urls - previous_urls,
            'removed': previous_urls - current_urls,
            'unchanged': current_urls & previous_urls
        }

    def run_discovery(self) -> Dict:
        """
        Execute full discovery process for all sections.

        Returns:
            Discovery report with statistics
        """
        logger.info("Starting Discovery Agent run...")
        base_url = self.site_map['base_url']

        # First, try to get URLs from sitemap
        sitemap_urls = self.fetch_sitemap_xml(base_url)
        logger.info(f"Found {len(sitemap_urls)} URLs from sitemap")

        # Process each section
        for section_name, section_config in self.site_map['sections'].items():
            logger.info(f"Processing section: {section_name}")

            # Get previous URLs for this section
            previous_urls = set(section_config.get('discovered_urls', []))

            # Discover URLs from sitemap
            section_sitemap_urls = {
                url for url in sitemap_urls
                if self._matches_patterns(url, section_config['url_patterns'])
            }

            # Discover additional URLs by crawling
            crawled_urls = set()
            for pattern in section_config['url_patterns']:
                # Get base URL from pattern
                pattern_base = pattern.replace('*', '')
                if pattern_base.endswith('/'):
                    pattern_base = pattern_base[:-1]

                crawled = self.discover_urls_by_crawl(
                    pattern_base,
                    section_config['url_patterns'],
                    max_depth=self.site_map['global_settings'].get('max_depth', 3)
                )
                crawled_urls.update(crawled)

            # Combine all discovered URLs
            current_urls = section_sitemap_urls | crawled_urls

            # Detect changes
            changes = self.detect_changes(section_name, current_urls, previous_urls)

            # Update site map
            self.site_map['sections'][section_name]['discovered_urls'] = list(current_urls)
            self.site_map['sections'][section_name]['url_count'] = len(current_urls)
            self.site_map['sections'][section_name]['last_discovery'] = datetime.now(timezone.utc).isoformat()

            # Track changes
            if changes['new']:
                self.changes['new_urls'].extend(list(changes['new']))
                logger.info(f"  New URLs: {len(changes['new'])}")
            if changes['removed']:
                self.changes['removed_urls'].extend(list(changes['removed']))
                logger.info(f"  Removed URLs: {len(changes['removed'])}")

            logger.info(f"  Total URLs: {len(current_urls)}")

        # Save updated site map
        self._save_site_map()

        # Generate report
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_sections': len(self.site_map['sections']),
            'total_urls': sum(section.get('url_count', 0) for section in self.site_map['sections'].values()),
            'new_urls_count': len(self.changes['new_urls']),
            'removed_urls_count': len(self.changes['removed_urls']),
            'changes': self.changes
        }

        logger.info("Discovery Agent run completed")
        logger.info(f"Report: {json.dumps(report, indent=2)}")

        return report


def main():
    """Main entry point for Discovery Agent."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    config_path = os.getenv(
        'SITE_MAP_CONFIG_PATH',
        './configs/site_map/SITE_MAP.json'
    )

    agent = DiscoveryAgent(config_path)
    report = agent.run_discovery()

    # Save report
    report_path = Path('./data/processed') / f"discovery_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Discovery report saved to {report_path}")


if __name__ == "__main__":
    main()
