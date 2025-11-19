"""
Scraper Agent - Renders dynamic pages with Playwright, respects rate limits.
Schedule: Daily 02:00 IST + on-demand
"""
import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import boto3
from playwright.async_api import async_playwright, Page, Browser
from loguru import logger
import redis


class RateLimiter:
    """Redis-based rate limiter for respectful scraping."""

    def __init__(self, rate_limit_rps: float = 2.0, redis_client: Optional[redis.Redis] = None):
        """
        Initialize rate limiter.

        Args:
            rate_limit_rps: Requests per second limit
            redis_client: Redis client for distributed rate limiting
        """
        self.rate_limit_rps = rate_limit_rps
        self.min_interval = 1.0 / rate_limit_rps
        self.last_request_time = 0
        self.redis_client = redis_client
        self.redis_key = "bmf:scraper:last_request"

    async def acquire(self):
        """Wait if necessary to respect rate limit."""
        if self.redis_client:
            # Distributed rate limiting
            while True:
                last_request = self.redis_client.get(self.redis_key)
                if last_request:
                    elapsed = time.time() - float(last_request)
                    if elapsed < self.min_interval:
                        await asyncio.sleep(self.min_interval - elapsed)
                    else:
                        break
                else:
                    break

            self.redis_client.set(self.redis_key, str(time.time()))
        else:
            # Local rate limiting
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


class ScraperAgent:
    """Agent responsible for scraping web pages with Playwright."""

    def __init__(
        self,
        site_map_path: str,
        output_dir: str = "./data/raw/html",
        s3_bucket: Optional[str] = None,
        rate_limit_rps: float = 2.0,
        enable_screenshots: bool = True
    ):
        """
        Initialize Scraper Agent.

        Args:
            site_map_path: Path to SITE_MAP.json
            output_dir: Local directory for scraped content
            s3_bucket: S3 bucket for raw HTML storage
            rate_limit_rps: Requests per second limit
            enable_screenshots: Whether to capture screenshots
        """
        self.site_map_path = Path(site_map_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.s3_bucket = s3_bucket
        self.s3_client = boto3.client('s3') if s3_bucket else None
        self.enable_screenshots = enable_screenshots
        self.rate_limiter = RateLimiter(rate_limit_rps)
        self.site_map = self._load_site_map()
        self.stats = {
            'total_urls': 0,
            'successful_scrapes': 0,
            'failed_scrapes': 0,
            'skipped_urls': 0
        }

    def _load_site_map(self) -> Dict:
        """Load SITE_MAP configuration."""
        with open(self.site_map_path, 'r') as f:
            return json.load(f)

    async def _init_browser(self) -> Browser:
        """Initialize Playwright browser with proper configuration."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        return browser

    async def _scrape_page(
        self,
        page: Page,
        url: str,
        section: str,
        selectors: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        Scrape a single page.

        Args:
            page: Playwright page instance
            url: URL to scrape
            section: Section name from SITE_MAP
            selectors: CSS selectors for extracting specific elements

        Returns:
            Scraped content and metadata
        """
        await self.rate_limiter.acquire()

        logger.info(f"Scraping: {url}")

        try:
            # Navigate with realistic delays
            await page.goto(url, wait_until='networkidle', timeout=30000)

            # Human-like delay
            await asyncio.sleep(0.5 + (hash(url) % 1000) / 1000)

            # Get page content
            html_content = await page.content()

            # Extract structured data using selectors
            structured_data = {}
            if selectors:
                for key, selector in selectors.items():
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            structured_data[key] = await element.inner_text()
                    except Exception as e:
                        logger.warning(f"Failed to extract {key} from {url}: {e}")

            # Get page title and meta
            title = await page.title()
            url_final = page.url  # After redirects

            # Take screenshot if enabled
            screenshot_path = None
            if self.enable_screenshots:
                screenshot_filename = f"{hashlib.md5(url.encode()).hexdigest()}.png"
                screenshot_path = self.output_dir / section / "screenshots" / screenshot_filename
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path), full_page=True)

            # Create metadata
            metadata = {
                'url': url,
                'final_url': url_final,
                'title': title,
                'section': section,
                'scraped_at': datetime.now(timezone.utc).isoformat(),
                'content_hash': hashlib.sha256(html_content.encode()).hexdigest(),
                'structured_data': structured_data,
                'screenshot_path': str(screenshot_path) if screenshot_path else None,
                'success': True
            }

            # Save HTML locally
            html_filename = f"{hashlib.md5(url.encode()).hexdigest()}.html"
            html_path = self.output_dir / section / html_filename
            html_path.parent.mkdir(parents=True, exist_ok=True)

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # Upload to S3 if configured
            if self.s3_client and self.s3_bucket:
                s3_key = f"raw-html/{datetime.now().strftime('%Y-%m-%d')}/{section}/{html_filename}"
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=html_content.encode('utf-8'),
                    ContentType='text/html',
                    Metadata={
                        'url': url,
                        'section': section,
                        'scraped_at': metadata['scraped_at']
                    }
                )
                metadata['s3_key'] = s3_key

            self.stats['successful_scrapes'] += 1
            logger.info(f"Successfully scraped: {url}")

            return metadata

        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            self.stats['failed_scrapes'] += 1
            return {
                'url': url,
                'section': section,
                'scraped_at': datetime.now(timezone.utc).isoformat(),
                'success': False,
                'error': str(e)
            }

    async def scrape_section(
        self,
        section_name: str,
        url_limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Scrape all URLs in a section.

        Args:
            section_name: Name of section from SITE_MAP
            url_limit: Optional limit on number of URLs to scrape

        Returns:
            List of scrape results
        """
        section_config = self.site_map['sections'].get(section_name)
        if not section_config:
            logger.error(f"Section '{section_name}' not found in SITE_MAP")
            return []

        urls = section_config.get('discovered_urls', [])
        if url_limit:
            urls = urls[:url_limit]

        self.stats['total_urls'] += len(urls)

        logger.info(f"Scraping section '{section_name}': {len(urls)} URLs")

        browser = await self._init_browser()
        context = await browser.new_context(
            user_agent=self.site_map['global_settings']['user_agent'],
            viewport={'width': 1920, 'height': 1080},
            locale='en-IN'
        )
        page = await context.new_page()

        results = []
        selectors = section_config.get('selectors', {})

        for url in urls:
            result = await self._scrape_page(page, url, section_name, selectors)
            results.append(result)

        await browser.close()

        return results

    async def scrape_all_sections(
        self,
        sections: Optional[List[str]] = None,
        url_limit_per_section: Optional[int] = None
    ) -> Dict:
        """
        Scrape all sections (or specified sections).

        Args:
            sections: Optional list of section names to scrape
            url_limit_per_section: Optional limit per section

        Returns:
            Complete scraping report
        """
        logger.info("Starting Scraper Agent run...")

        if sections is None:
            sections = list(self.site_map['sections'].keys())

        all_results = {}

        for section in sections:
            results = await self.scrape_section(section, url_limit_per_section)
            all_results[section] = results

        # Generate report
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sections_scraped': len(sections),
            'stats': self.stats,
            'results': all_results
        }

        # Save report
        report_path = self.output_dir / f"scraper_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info("Scraper Agent run completed")
        logger.info(f"Stats: {json.dumps(self.stats, indent=2)}")
        logger.info(f"Report saved to {report_path}")

        return report


async def main():
    """Main entry point for Scraper Agent."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    site_map_path = os.getenv(
        'SITE_MAP_CONFIG_PATH',
        './configs/site_map/SITE_MAP.json'
    )
    output_dir = os.getenv('SCRAPER_OUTPUT_DIR', './data/raw/html')
    s3_bucket = os.getenv('S3_BUCKET_RAW')
    rate_limit_rps = float(os.getenv('SCRAPE_RATE_LIMIT', '2.0'))
    enable_screenshots = os.getenv('ENABLE_SCREENSHOTS', 'true').lower() == 'true'

    agent = ScraperAgent(
        site_map_path=site_map_path,
        output_dir=output_dir,
        s3_bucket=s3_bucket,
        rate_limit_rps=rate_limit_rps,
        enable_screenshots=enable_screenshots
    )

    report = await agent.scrape_all_sections()

    logger.info(f"Scraping completed: {report['stats']}")


if __name__ == "__main__":
    asyncio.run(main())
