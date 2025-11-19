#!/usr/bin/env python3
"""
BMF RAG Platform Management CLI
Usage: python manage.py <command> [options]
"""
import argparse
import asyncio
import sys
from pathlib import Path
from loguru import logger


def setup_logging(verbose: bool = False):
    """Configure logging."""
    logger.remove()
    log_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=log_level
    )


def cmd_discovery(args):
    """Run Discovery Agent."""
    from agents.discovery.discovery_agent import DiscoveryAgent

    logger.info("Running Discovery Agent...")
    agent = DiscoveryAgent(args.config)
    report = agent.run_discovery()
    logger.success(f"Discovery completed: {report['total_urls']} total URLs")


def cmd_scrape(args):
    """Run Scraper Agent."""
    from agents.scraper.scraper_agent import ScraperAgent

    logger.info("Running Scraper Agent...")
    agent = ScraperAgent(
        site_map_path=args.config,
        output_dir=args.output,
        rate_limit_rps=args.rate_limit
    )

    sections = [args.section] if args.section else None
    report = asyncio.run(agent.scrape_all_sections(
        sections=sections,
        url_limit_per_section=args.limit
    ))

    logger.success(f"Scraping completed: {report['stats']}")


def cmd_harvest(args):
    """Run Document Harvester."""
    from agents.document_harvester.harvester_agent import DocumentHarvester

    logger.info("Running Document Harvester...")
    harvester = DocumentHarvester(
        site_map_path=args.config,
        html_dir=args.html_dir,
        output_dir=args.output
    )

    report = harvester.harvest_all_sections()
    logger.success(f"Harvesting completed: {report['stats']}")


def cmd_query(args):
    """Query the RAG copilot."""
    from src.rag_copilot.claude_rag_copilot import ClaudeRAGCopilot

    logger.info(f"Querying RAG copilot: {args.query}")

    copilot = ClaudeRAGCopilot()
    response = copilot.query(args.query)

    print("\n" + "="*80)
    print(f"Query: {args.query}")
    print("="*80)
    print(f"\nConfidence: {response.confidence.value}")
    print(f"Investor Type: {response.investor_type.value}")
    print(f"\nAnswer:\n{response.answer}")
    print(f"\nCitations ({len(response.citations)}):")
    for citation in response.citations:
        print(f"  - {citation['source_url']} (score: {citation['score']:.2f})")
    print("="*80 + "\n")


def cmd_validate(args):
    """Run validation tests."""
    logger.info("Running validation tests...")

    # Run pytest on tests directory
    import subprocess
    result = subprocess.run(
        ['pytest', 'tests/', '-v', '--tb=short'],
        capture_output=False
    )

    sys.exit(result.returncode)


def cmd_pipeline(args):
    """Run full pipeline."""
    logger.info("Running full BMF RAG pipeline...")

    # Run agents in sequence
    from agents.discovery.discovery_agent import DiscoveryAgent
    from agents.scraper.scraper_agent import ScraperAgent
    from agents.document_harvester.harvester_agent import DocumentHarvester

    config = args.config

    # 1. Discovery
    logger.info("Step 1/7: Discovery Agent")
    discovery = DiscoveryAgent(config)
    discovery.run_discovery()

    # 2. Scraper
    logger.info("Step 2/7: Scraper Agent")
    scraper = ScraperAgent(site_map_path=config)
    asyncio.run(scraper.scrape_all_sections())

    # 3. Harvester
    logger.info("Step 3/7: Document Harvester")
    harvester = DocumentHarvester(site_map_path=config)
    harvester.harvest_all_sections()

    # 4-7 would go here (Parser, Chunker, Validator, Monitoring)
    logger.info("Step 4/7: Parser Agent (not yet implemented)")
    logger.info("Step 5/7: Chunk Orchestrator (not yet implemented)")
    logger.info("Step 6/7: Validator Agent (not yet implemented)")
    logger.info("Step 7/7: Monitoring Agent (not yet implemented)")

    logger.success("Pipeline execution completed!")


def cmd_init(args):
    """Initialize the BMF RAG platform."""
    logger.info("Initializing BMF RAG platform...")

    # Create necessary directories
    dirs = [
        'data/raw/html',
        'data/raw/pdf',
        'data/processed',
        'data/cache',
        'logs'
    ]

    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {dir_path}")

    # Create .env from .env.example if not exists
    env_file = Path('.env')
    if not env_file.exists() and Path('.env.example').exists():
        import shutil
        shutil.copy('.env.example', '.env')
        logger.info("Created .env from .env.example")
        logger.warning("Please update .env with your actual credentials")

    # Install Playwright browsers
    logger.info("Installing Playwright browsers...")
    import subprocess
    subprocess.run(['playwright', 'install', 'chromium'])

    logger.success("Initialization complete!")
    logger.info("Next steps:")
    logger.info("  1. Update .env with your credentials")
    logger.info("  2. Run: python manage.py discovery")
    logger.info("  3. Run: python manage.py pipeline")


def cmd_status(args):
    """Show platform status."""
    import json
    from datetime import datetime

    logger.info("BMF RAG Platform Status")
    print("\n" + "="*80)
    print("BMF RAG PLATFORM STATUS")
    print("="*80)

    # Check data directories
    print("\nData Directories:")
    data_dirs = {
        'Raw HTML': Path('data/raw/html'),
        'Raw PDF': Path('data/raw/pdf'),
        'Processed': Path('data/processed'),
        'Cache': Path('data/cache')
    }

    for name, path in data_dirs.items():
        if path.exists():
            file_count = len(list(path.rglob('*')))
            print(f"  {name}: ✓ ({file_count} files)")
        else:
            print(f"  {name}: ✗ (not created)")

    # Check latest reports
    print("\nLatest Reports:")
    reports = {
        'Discovery': list(Path('data/processed').glob('discovery_report_*.json')),
        'Scraper': list(Path('data/raw/html').glob('scraper_report_*.json')),
        'Harvester': list(Path('data/raw/pdf').glob('harvest_report_*.json'))
    }

    for name, report_files in reports.items():
        if report_files:
            latest = max(report_files, key=lambda p: p.stat().st_mtime)
            mtime = datetime.fromtimestamp(latest.stat().st_mtime)
            print(f"  {name}: {latest.name} ({mtime.strftime('%Y-%m-%d %H:%M')})")
        else:
            print(f"  {name}: No reports found")

    print("\n" + "="*80 + "\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='BMF RAG Platform Management CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manage.py init                           # Initialize platform
  python manage.py discovery                      # Run discovery agent
  python manage.py scrape --section funds         # Scrape funds section
  python manage.py harvest                        # Harvest documents
  python manage.py query "What is the NAV of..."  # Query RAG copilot
  python manage.py pipeline                       # Run full pipeline
  python manage.py validate                       # Run validation tests
  python manage.py status                         # Show platform status
        """
    )

    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize platform')

    # Discovery command
    discovery_parser = subparsers.add_parser('discovery', help='Run Discovery Agent')
    discovery_parser.add_argument(
        '--config',
        default='./configs/site_map/SITE_MAP.json',
        help='Path to SITE_MAP.json'
    )

    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Run Scraper Agent')
    scrape_parser.add_argument(
        '--config',
        default='./configs/site_map/SITE_MAP.json',
        help='Path to SITE_MAP.json'
    )
    scrape_parser.add_argument(
        '--output',
        default='./data/raw/html',
        help='Output directory'
    )
    scrape_parser.add_argument(
        '--section',
        help='Specific section to scrape'
    )
    scrape_parser.add_argument(
        '--limit',
        type=int,
        help='Limit URLs per section'
    )
    scrape_parser.add_argument(
        '--rate-limit',
        type=float,
        default=2.0,
        help='Requests per second limit'
    )

    # Harvest command
    harvest_parser = subparsers.add_parser('harvest', help='Run Document Harvester')
    harvest_parser.add_argument(
        '--config',
        default='./configs/site_map/SITE_MAP.json',
        help='Path to SITE_MAP.json'
    )
    harvest_parser.add_argument(
        '--html-dir',
        default='./data/raw/html',
        help='HTML input directory'
    )
    harvest_parser.add_argument(
        '--output',
        default='./data/raw/pdf',
        help='Output directory'
    )

    # Query command
    query_parser = subparsers.add_parser('query', help='Query RAG copilot')
    query_parser.add_argument('query', help='Query string')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Run validation tests')

    # Pipeline command
    pipeline_parser = subparsers.add_parser('pipeline', help='Run full pipeline')
    pipeline_parser.add_argument(
        '--config',
        default='./configs/site_map/SITE_MAP.json',
        help='Path to SITE_MAP.json'
    )

    # Status command
    status_parser = subparsers.add_parser('status', help='Show platform status')

    args = parser.parse_args()

    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Command routing
    commands = {
        'init': cmd_init,
        'discovery': cmd_discovery,
        'scrape': cmd_scrape,
        'harvest': cmd_harvest,
        'query': cmd_query,
        'validate': cmd_validate,
        'pipeline': cmd_pipeline,
        'status': cmd_status
    }

    try:
        commands[args.command](args)
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
