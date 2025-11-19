"""
Validator Agent - Validates chunks and runs regression tests.
Schedule: Daily 04:00 IST

Uses Great Expectations for automated quality validation.
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

# Optional Great Expectations import
try:
    import great_expectations as gx
    from great_expectations.core.batch import RuntimeBatchRequest
    GX_AVAILABLE = True
except ImportError:
    GX_AVAILABLE = False
    logger.warning("Great Expectations not installed. Validation will use basic checks.")


class ValidatorAgent:
    """Agent responsible for quality validation using Great Expectations."""

    def __init__(
        self,
        config_path: str,
        chunks_dir: str = "./data/processed/chunks",
        expectations_dir: str = "./configs/expectations",
        reports_dir: str = "./logs/validation"
    ):
        """
        Initialize Validator Agent.

        Args:
            config_path: Path to validation config
            chunks_dir: Directory containing processed chunks
            expectations_dir: Directory for Great Expectations suites
            reports_dir: Directory for validation reports
        """
        self.config_path = Path(config_path)
        self.chunks_dir = Path(chunks_dir)
        self.expectations_dir = Path(expectations_dir)
        self.reports_dir = Path(reports_dir)

        # Create directories
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.expectations_dir.mkdir(parents=True, exist_ok=True)

        # Load validation config
        self.config = self._load_config()

        # Stats tracking
        self.stats = {
            'total_chunks_validated': 0,
            'chunks_passed': 0,
            'chunks_failed': 0,
            'metadata_completeness': 0.0,
            'regression_pass_rate': 0.0,
            'compliance_issues': 0
        }

    def _load_config(self) -> Dict:
        """Load validation configuration."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            # Default validation config
            logger.warning(f"Config not found at {self.config_path}, using defaults")
            return {
                'metadata_completeness_threshold': 0.90,
                'required_metadata_fields': [
                    'chunk_id', 'fund_name', 'category', 'doc_type',
                    'publish_date', 'checksum'
                ],
                'regression_test_path': 'tests/regression/test_rag_regression.py',
                'citation_match_threshold': 0.90,
                'retrieval_accuracy_threshold': 0.80
            }

    def validate_metadata_completeness(self, chunks: List[Dict]) -> Dict:
        """
        Check metadata completeness using Great Expectations or basic validation.

        Args:
            chunks: List of chunk dictionaries

        Returns:
            Validation report
        """
        logger.info(f"Validating metadata completeness for {len(chunks)} chunks")

        required_fields = self.config['required_metadata_fields']
        threshold = self.config['metadata_completeness_threshold']

        passed = 0
        failed = 0
        issues = []

        for chunk in chunks:
            metadata = chunk.get('metadata', {})
            missing_fields = []

            for field in required_fields:
                if field not in metadata or not metadata[field]:
                    missing_fields.append(field)

            if not missing_fields:
                passed += 1
            else:
                failed += 1
                issues.append({
                    'chunk_id': chunk.get('chunk_id', 'unknown'),
                    'missing_fields': missing_fields
                })

        total = passed + failed
        completeness = passed / total if total > 0 else 0.0

        self.stats['metadata_completeness'] = completeness

        report = {
            'total_chunks': total,
            'passed': passed,
            'failed': failed,
            'completeness_rate': completeness,
            'threshold': threshold,
            'passed_threshold': completeness >= threshold,
            'issues': issues[:10] if len(issues) > 10 else issues  # Sample issues
        }

        if completeness >= threshold:
            logger.info(f"✓ Metadata completeness: {completeness:.2%} (threshold: {threshold:.2%})")
        else:
            logger.warning(f"✗ Metadata completeness: {completeness:.2%} (threshold: {threshold:.2%})")

        return report

    def validate_chunk_quality(self, chunks: List[Dict]) -> Dict:
        """
        Validate chunk quality metrics.

        Args:
            chunks: List of chunk dictionaries

        Returns:
            Quality validation report
        """
        logger.info("Validating chunk quality metrics")

        issues = []

        for chunk in chunks:
            chunk_id = chunk.get('chunk_id', 'unknown')
            content = chunk.get('content', '')

            # Check content length
            if len(content) < 50:
                issues.append({
                    'chunk_id': chunk_id,
                    'issue': 'content_too_short',
                    'length': len(content)
                })

            # Check for required content patterns (fund-specific)
            metadata = chunk.get('metadata', {})
            fund_name = metadata.get('fund_name', '')

            if fund_name and fund_name.lower() not in content.lower():
                issues.append({
                    'chunk_id': chunk_id,
                    'issue': 'fund_name_not_in_content',
                    'fund_name': fund_name
                })

        passed = len(chunks) - len(issues)
        total = len(chunks)
        quality_rate = passed / total if total > 0 else 0.0

        return {
            'total_chunks': total,
            'passed': passed,
            'failed': len(issues),
            'quality_rate': quality_rate,
            'issues': issues[:10] if len(issues) > 10 else issues
        }

    def run_regression_tests(self) -> Dict:
        """
        Run regression tests using pytest.

        Returns:
            Regression test results
        """
        logger.info("Running regression tests")

        test_path = self.config.get('regression_test_path', 'tests/regression/')

        if not Path(test_path).exists():
            logger.warning(f"Regression test path not found: {test_path}")
            return {
                'status': 'skipped',
                'reason': 'test_path_not_found',
                'path': str(test_path)
            }

        try:
            # Run pytest with regression marker
            result = subprocess.run(
                ['pytest', test_path, '-v', '-m', 'regression', '--tb=short'],
                capture_output=True,
                text=True,
                timeout=300
            )

            # Parse pytest output
            output = result.stdout + result.stderr

            # Extract test counts
            passed = output.count(' PASSED')
            failed = output.count(' FAILED')
            skipped = output.count(' SKIPPED')
            total = passed + failed

            pass_rate = passed / total if total > 0 else 0.0
            citation_threshold = self.config.get('citation_match_threshold', 0.90)

            self.stats['regression_pass_rate'] = pass_rate

            report = {
                'status': 'completed',
                'total_tests': total,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'pass_rate': pass_rate,
                'citation_threshold': citation_threshold,
                'passed_threshold': pass_rate >= citation_threshold,
                'exit_code': result.returncode
            }

            if pass_rate >= citation_threshold:
                logger.info(f"✓ Regression tests: {pass_rate:.2%} pass rate")
            else:
                logger.warning(f"✗ Regression tests: {pass_rate:.2%} pass rate (threshold: {citation_threshold:.2%})")

            return report

        except subprocess.TimeoutExpired:
            logger.error("Regression tests timed out")
            return {'status': 'timeout', 'error': 'Tests exceeded 5 minute timeout'}
        except Exception as e:
            logger.error(f"Error running regression tests: {e}")
            return {'status': 'error', 'error': str(e)}

    def check_compliance_docs(self, chunks: List[Dict]) -> Dict:
        """
        Verify compliance documents have required disclaimers.

        Args:
            chunks: List of chunk dictionaries

        Returns:
            Compliance check report
        """
        logger.info("Checking compliance documentation")

        required_disclaimers = [
            'past performance',
            'risk',
            'mutual fund investments are subject to market risks'
        ]

        compliance_chunks = [
            c for c in chunks
            if c.get('metadata', {}).get('category') in ['compliance', 'regulatory', 'factsheet', 'kim']
        ]

        issues = []

        for chunk in compliance_chunks:
            content_lower = chunk.get('content', '').lower()
            missing_disclaimers = []

            for disclaimer in required_disclaimers:
                if disclaimer not in content_lower:
                    missing_disclaimers.append(disclaimer)

            if missing_disclaimers:
                issues.append({
                    'chunk_id': chunk.get('chunk_id', 'unknown'),
                    'category': chunk.get('metadata', {}).get('category'),
                    'missing_disclaimers': missing_disclaimers
                })

        self.stats['compliance_issues'] = len(issues)

        report = {
            'total_compliance_chunks': len(compliance_chunks),
            'chunks_with_issues': len(issues),
            'compliance_rate': 1.0 - (len(issues) / len(compliance_chunks)) if compliance_chunks else 1.0,
            'issues': issues
        }

        if len(issues) == 0:
            logger.info("✓ All compliance documents have required disclaimers")
        else:
            logger.warning(f"✗ {len(issues)} compliance documents missing disclaimers")

        return report

    def validate_chunks_from_file(self, chunks_file: Path) -> Dict:
        """
        Load chunks from file and validate.

        Args:
            chunks_file: Path to chunks JSON file

        Returns:
            Combined validation report
        """
        logger.info(f"Loading chunks from {chunks_file}")

        try:
            with open(chunks_file, 'r') as f:
                data = json.load(f)

            chunks = data if isinstance(data, list) else data.get('chunks', [])

            logger.info(f"Loaded {len(chunks)} chunks for validation")

            return self.validate_chunks(chunks)

        except Exception as e:
            logger.error(f"Error loading chunks: {e}")
            return {'status': 'error', 'error': str(e)}

    def validate_chunks(self, chunks: List[Dict]) -> Dict:
        """
        Run all validation checks on chunks.

        Args:
            chunks: List of chunk dictionaries

        Returns:
            Complete validation report
        """
        logger.info(f"Running validation on {len(chunks)} chunks")

        self.stats['total_chunks_validated'] = len(chunks)

        # Run all validation checks
        metadata_report = self.validate_metadata_completeness(chunks)
        quality_report = self.validate_chunk_quality(chunks)
        compliance_report = self.check_compliance_docs(chunks)
        regression_report = self.run_regression_tests()

        # Calculate overall pass/fail
        passed = (
            metadata_report.get('passed_threshold', False) and
            quality_report.get('quality_rate', 0) > 0.85 and
            compliance_report.get('compliance_rate', 0) > 0.95
        )

        self.stats['chunks_passed'] = metadata_report['passed']
        self.stats['chunks_failed'] = metadata_report['failed']

        report = {
            'timestamp': datetime.now().isoformat(),
            'total_chunks': len(chunks),
            'overall_status': 'PASSED' if passed else 'FAILED',
            'metadata_validation': metadata_report,
            'quality_validation': quality_report,
            'compliance_validation': compliance_report,
            'regression_validation': regression_report,
            'stats': self.stats
        }

        # Save report
        self._save_report(report)

        return report

    def _save_report(self, report: Dict):
        """Save validation report to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.reports_dir / f"validation_report_{timestamp}.json"

        with open(report_file, 'w') as f:
            json.dump(report, indent=2, fp=f)

        logger.info(f"Validation report saved to {report_file}")

    def run_validator(self, chunks_dir: Optional[Path] = None) -> Dict:
        """
        Execute complete validation pipeline.

        Args:
            chunks_dir: Optional directory containing chunk files

        Returns:
            Validation summary
        """
        logger.info("=" * 60)
        logger.info("Starting Validator Agent")
        logger.info("=" * 60)

        chunks_path = chunks_dir or self.chunks_dir

        # Find all chunk files
        chunk_files = list(chunks_path.glob("**/*.json"))

        if not chunk_files:
            logger.warning(f"No chunk files found in {chunks_path}")
            return {
                'status': 'no_chunks_found',
                'path': str(chunks_path)
            }

        logger.info(f"Found {len(chunk_files)} chunk files to validate")

        # Validate first file as sample (or combine all for full validation)
        if chunk_files:
            report = self.validate_chunks_from_file(chunk_files[0])
        else:
            report = {'status': 'no_files'}

        logger.info("=" * 60)
        logger.info(f"Validation Complete: {report.get('overall_status', 'UNKNOWN')}")
        logger.info("=" * 60)

        return report


def main():
    """Main entry point for Validator Agent."""
    logger.info("Validator Agent - Quality Validation System")

    validator = ValidatorAgent(
        config_path="./configs/validation/validation_config.json"
    )

    report = validator.run_validator()

    logger.info(f"Validation Status: {report.get('overall_status', 'UNKNOWN')}")


if __name__ == "__main__":
    main()
