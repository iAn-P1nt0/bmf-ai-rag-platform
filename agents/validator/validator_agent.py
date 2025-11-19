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

        reporting_cfg = self.config.get('reporting', {})
        self.issue_sample_limit = reporting_cfg.get('max_issue_samples', 10)

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
                'quality_rate_threshold': 0.85,
                'compliance_rate_threshold': 0.95,
                'required_metadata_fields': [
                    'chunk_id', 'fund_name', 'category', 'doc_type',
                    'publish_date', 'checksum'
                ],
                'optional_metadata_fields': [],
                'regression_test_path': 'tests/regression/test_rag_regression.py',
                'citation_match_threshold': 0.90,
                'retrieval_accuracy_threshold': 0.80,
                'great_expectations': {
                    'enabled': False,
                    'suite_path': ''
                },
                'reporting': {
                    'max_issue_samples': 10
                }
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
            'issues': issues[:self.issue_sample_limit]
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

        threshold = self.config.get('quality_rate_threshold', 0.85)

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
            'threshold': threshold,
            'passed_threshold': quality_rate >= threshold,
            'issues': issues[:self.issue_sample_limit]
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

        compliance_categories = self.config.get(
            'compliance_categories',
            ['compliance', 'regulatory', 'factsheet', 'kim']
        )

        compliance_chunks = [
            c for c in chunks
            if c.get('metadata', {}).get('category') in compliance_categories
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

        threshold = self.config.get('compliance_rate_threshold', 0.95)

        compliance_rate = 1.0 - (len(issues) / len(compliance_chunks)) if compliance_chunks else 1.0

        report = {
            'total_compliance_chunks': len(compliance_chunks),
            'chunks_with_issues': len(issues),
            'compliance_rate': compliance_rate,
            'threshold': threshold,
            'passed_threshold': compliance_rate >= threshold,
            'issues': issues[:self.issue_sample_limit]
        }

        if len(issues) == 0:
            logger.info("✓ All compliance documents have required disclaimers")
        else:
            logger.warning(f"✗ {len(issues)} compliance documents missing disclaimers")

        return report

    def _prepare_chunk_dataframe(self, chunks: List[Dict]):
        """Flatten chunk metadata for Great Expectations."""
        try:
            import pandas as pd
        except ImportError:
            logger.warning("Pandas not installed. Skipping Great Expectations suite.")
            return None

        rows = []
        required_fields = self.config.get('required_metadata_fields', [])
        optional_fields = self.config.get('optional_metadata_fields', [])
        fields_to_capture = list(dict.fromkeys(required_fields + optional_fields))

        for chunk in chunks:
            metadata = chunk.get('metadata', {})
            row = {
                'chunk_id': chunk.get('chunk_id'),
                'token_count': chunk.get('token_count', 0),
                'content_length': len(chunk.get('content', '') or ''),
                'checksum': metadata.get('checksum') or chunk.get('checksum'),
                'publish_date': metadata.get('publish_date'),
                'category': metadata.get('category'),
                'doc_type': metadata.get('doc_type'),
                'risk_profile': metadata.get('risk_profile'),
                'source_url': metadata.get('source_url')
            }

            for field in fields_to_capture:
                row[field] = metadata.get(field)

            rows.append(row)

        if not rows:
            return None

        return pd.DataFrame(rows)

    def run_great_expectations_suite(self, chunks: List[Dict]) -> Dict:
        """Run configured Great Expectations suite against chunk dataframe."""
        gx_config = self.config.get('great_expectations', {})
        if not gx_config.get('enabled', False):
            return {'status': 'skipped', 'reason': 'disabled_in_config'}

        if not GX_AVAILABLE:
            return {'status': 'skipped', 'reason': 'great_expectations_not_installed'}

        suite_path = gx_config.get('suite_path')
        if not suite_path:
            return {'status': 'skipped', 'reason': 'suite_path_not_configured'}

        suite_file = Path(suite_path)
        if not suite_file.exists():
            return {'status': 'skipped', 'reason': 'suite_file_missing', 'path': suite_path}

        df = self._prepare_chunk_dataframe(chunks)
        if df is None:
            return {'status': 'skipped', 'reason': 'no_data_frame'}

        try:
            with open(suite_file, 'r') as f:
                suite_definition = json.load(f)
        except Exception as exc:
            logger.error(f"Failed to load expectation suite: {exc}")
            return {'status': 'error', 'error': str(exc)}

        expectations = suite_definition.get('expectations', [])
        if not expectations:
            return {'status': 'skipped', 'reason': 'no_expectations_defined'}

        try:
            from great_expectations.dataset import PandasDataset  # type: ignore
        except ImportError as exc:
            logger.warning(f"Great Expectations PandasDataset unavailable: {exc}")
            return {'status': 'skipped', 'reason': 'pandas_dataset_unavailable'}

        dataset = PandasDataset(df)
        results = []
        overall_success = True

        for expectation in expectations:
            expectation_type = expectation.get('expectation_type')
            kwargs = expectation.get('kwargs', {})
            notes = expectation.get('notes')

            if not expectation_type:
                continue

            expectation_fn = getattr(dataset, expectation_type, None)
            if not expectation_fn:
                logger.warning(f"Expectation {expectation_type} not supported by PandasDataset")
                results.append({
                    'expectation_type': expectation_type,
                    'status': 'unsupported'
                })
                continue

            try:
                result = expectation_fn(**kwargs)
                success = bool(result.success)
                overall_success = overall_success and success
                results.append({
                    'expectation_type': expectation_type,
                    'success': success,
                    'kwargs': kwargs,
                    'notes': notes
                })
            except Exception as exc:
                overall_success = False
                logger.error(f"Expectation {expectation_type} failed: {exc}")
                results.append({
                    'expectation_type': expectation_type,
                    'success': False,
                    'error': str(exc),
                    'status': 'error'
                })

        status = 'completed' if overall_success else 'failed'

        return {
            'status': status,
            'success': overall_success,
            'suite_name': suite_definition.get('suite_name', gx_config.get('suite_name')),
            'results': results
        }

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
        gx_report = self.run_great_expectations_suite(chunks)

        # Calculate overall pass/fail
        passed = (
            metadata_report.get('passed_threshold', False) and
            quality_report.get('passed_threshold', False) and
            compliance_report.get('passed_threshold', False) and
            gx_report.get('status') in ['completed', 'skipped'] and
            gx_report.get('success', True)
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
            'great_expectations_validation': gx_report,
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
            json.dump(report, f, indent=2)

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
