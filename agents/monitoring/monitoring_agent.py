"""
Monitoring Agent - Tracks KPIs and manages alerts using Prometheus.
Schedule: 24/7 (5 minute intervals)

Monitors:
- Query latency (P95, P99)
- Retrieval accuracy
- Metadata staleness
- System drift
"""
import json
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque
from loguru import logger

# Optional Prometheus import
try:
    from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server, CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client not installed. Metrics will be logged only.")


class MetricsCollector:
    """Collects and tracks system metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self.registry = CollectorRegistry() if PROMETHEUS_AVAILABLE else None

        if PROMETHEUS_AVAILABLE:
            # Query metrics
            self.query_counter = Counter(
                'rag_queries_total',
                'Total number of RAG queries',
                ['investor_type', 'status'],
                registry=self.registry
            )

            self.query_latency = Histogram(
                'rag_query_latency_seconds',
                'Query latency in seconds',
                ['endpoint'],
                buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 5.0],
                registry=self.registry
            )

            # Retrieval metrics
            self.retrieval_accuracy = Gauge(
                'rag_retrieval_accuracy',
                'Retrieval accuracy percentage',
                registry=self.registry
            )

            self.chunk_staleness = Gauge(
                'rag_chunk_staleness_percentage',
                'Percentage of stale chunks',
                registry=self.registry
            )

            # System metrics
            self.active_chunks = Gauge(
                'rag_active_chunks_total',
                'Total number of active chunks',
                registry=self.registry
            )

        # In-memory storage for recent metrics
        self.recent_latencies = deque(maxlen=1000)
        self.recent_accuracy = deque(maxlen=100)
        self.metrics_history = []

    def record_query(self, investor_type: str, status: str, latency_seconds: float):
        """Record a query execution."""
        if PROMETHEUS_AVAILABLE:
            self.query_counter.labels(investor_type=investor_type, status=status).inc()
            self.query_latency.labels(endpoint='rag_query').observe(latency_seconds)

        self.recent_latencies.append(latency_seconds)

    def record_accuracy(self, accuracy: float):
        """Record retrieval accuracy."""
        if PROMETHEUS_AVAILABLE:
            self.retrieval_accuracy.set(accuracy)

        self.recent_accuracy.append(accuracy)

    def get_latency_percentiles(self) -> Dict[str, float]:
        """Calculate latency percentiles."""
        if not self.recent_latencies:
            return {'p50': 0, 'p95': 0, 'p99': 0}

        sorted_latencies = sorted(self.recent_latencies)
        n = len(sorted_latencies)

        return {
            'p50': sorted_latencies[int(n * 0.50)] if n > 0 else 0,
            'p95': sorted_latencies[int(n * 0.95)] if n > 0 else 0,
            'p99': sorted_latencies[int(n * 0.99)] if n > 0 else 0,
            'count': n
        }

    def get_average_accuracy(self) -> float:
        """Get average retrieval accuracy."""
        if not self.recent_accuracy:
            return 0.0
        return sum(self.recent_accuracy) / len(self.recent_accuracy)


class MonitoringAgent:
    """Agent responsible for monitoring and alerting."""

    def __init__(
        self,
        alerts_config: str,
        metrics_port: int = 8000,
        enable_prometheus: bool = True
    ):
        """
        Initialize Monitoring Agent.

        Args:
            alerts_config: Path to alerts.yml
            metrics_port: Port for Prometheus metrics server
            enable_prometheus: Whether to start Prometheus HTTP server
        """
        self.alerts_config_path = Path(alerts_config)
        self.metrics_port = metrics_port
        self.enable_prometheus = enable_prometheus and PROMETHEUS_AVAILABLE

        # Load alert configuration
        self.alerts_config = self._load_alerts_config()

        # Initialize metrics collector
        self.metrics = MetricsCollector()

        # Alert tracking
        self.active_alerts = []
        self.alert_history = deque(maxlen=100)

        # Start Prometheus server if enabled
        if self.enable_prometheus:
            try:
                start_http_server(self.metrics_port, registry=self.metrics.registry)
                logger.info(f"Prometheus metrics server started on port {self.metrics_port}")
            except Exception as e:
                logger.warning(f"Could not start Prometheus server: {e}")

    def _load_alerts_config(self) -> Dict:
        """Load alerts configuration."""
        if self.alerts_config_path.exists():
            with open(self.alerts_config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            logger.warning(f"Alerts config not found at {self.alerts_config_path}, using defaults")
            return {
                'thresholds': {
                    'latency_warning_ms': 500,
                    'latency_critical_ms': 900,
                    'accuracy_warning': 0.80,
                    'accuracy_critical': 0.70,
                    'staleness_warning': 0.03,
                    'drift_threshold': 0.05
                },
                'channels': {
                    'pagerduty': {'enabled': False},
                    'slack': {'enabled': False},
                    'email': {'enabled': False}
                }
            }

    def collect_latency_metrics(self, sample_queries: Optional[List[Dict]] = None) -> Dict:
        """
        Collect query latency metrics.

        Args:
            sample_queries: Optional list of sample queries to test

        Returns:
            Latency metrics report
        """
        logger.info("Collecting latency metrics")

        percentiles = self.metrics.get_latency_percentiles()

        thresholds = self.alerts_config.get('thresholds', {})
        warning_ms = thresholds.get('latency_warning_ms', 500)
        critical_ms = thresholds.get('latency_critical_ms', 900)

        p95_ms = percentiles['p95'] * 1000
        p99_ms = percentiles['p99'] * 1000

        status = 'healthy'
        if p95_ms > critical_ms:
            status = 'critical'
            self._trigger_alert({
                'type': 'latency_critical',
                'severity': 'critical',
                'message': f'P95 latency {p95_ms:.0f}ms exceeds critical threshold {critical_ms}ms',
                'metric': 'query_latency_p95',
                'value': p95_ms,
                'threshold': critical_ms
            })
        elif p95_ms > warning_ms:
            status = 'warning'
            self._trigger_alert({
                'type': 'latency_warning',
                'severity': 'warning',
                'message': f'P95 latency {p95_ms:.0f}ms exceeds warning threshold {warning_ms}ms',
                'metric': 'query_latency_p95',
                'value': p95_ms,
                'threshold': warning_ms
            })

        report = {
            'status': status,
            'p50_ms': percentiles['p50'] * 1000,
            'p95_ms': p95_ms,
            'p99_ms': p99_ms,
            'sample_count': percentiles['count'],
            'thresholds': {
                'warning': warning_ms,
                'critical': critical_ms
            }
        }

        logger.info(f"Latency: P50={report['p50_ms']:.0f}ms, P95={report['p95_ms']:.0f}ms, P99={report['p99_ms']:.0f}ms")

        return report

    def collect_accuracy_metrics(self) -> Dict:
        """
        Collect retrieval accuracy metrics.

        Returns:
            Accuracy metrics report
        """
        logger.info("Collecting accuracy metrics")

        avg_accuracy = self.metrics.get_average_accuracy()

        thresholds = self.alerts_config.get('thresholds', {})
        warning = thresholds.get('accuracy_warning', 0.80)
        critical = thresholds.get('accuracy_critical', 0.70)

        status = 'healthy'
        if avg_accuracy < critical:
            status = 'critical'
            self._trigger_alert({
                'type': 'accuracy_critical',
                'severity': 'critical',
                'message': f'Retrieval accuracy {avg_accuracy:.2%} below critical threshold {critical:.2%}',
                'metric': 'retrieval_accuracy',
                'value': avg_accuracy,
                'threshold': critical
            })
        elif avg_accuracy < warning:
            status = 'warning'
            self._trigger_alert({
                'type': 'accuracy_warning',
                'severity': 'warning',
                'message': f'Retrieval accuracy {avg_accuracy:.2%} below warning threshold {warning:.2%}',
                'metric': 'retrieval_accuracy',
                'value': avg_accuracy,
                'threshold': warning
            })

        report = {
            'status': status,
            'average_accuracy': avg_accuracy,
            'sample_count': len(self.metrics.recent_accuracy),
            'thresholds': {
                'warning': warning,
                'critical': critical
            }
        }

        logger.info(f"Accuracy: {avg_accuracy:.2%} (samples: {report['sample_count']})")

        return report

    def check_drift(self, current_metrics: Dict, baseline_metrics: Optional[Dict] = None) -> Dict:
        """
        Monitor drift in metrics week-over-week.

        Args:
            current_metrics: Current period metrics
            baseline_metrics: Baseline metrics for comparison

        Returns:
            Drift detection report
        """
        logger.info("Checking for metric drift")

        if not baseline_metrics:
            logger.warning("No baseline metrics provided, skipping drift check")
            return {'status': 'skipped', 'reason': 'no_baseline'}

        drift_threshold = self.alerts_config.get('thresholds', {}).get('drift_threshold', 0.05)

        accuracy_drift = abs(
            current_metrics.get('accuracy', 0) - baseline_metrics.get('accuracy', 0)
        )

        latency_drift = abs(
            current_metrics.get('latency_p95', 0) - baseline_metrics.get('latency_p95', 0)
        ) / baseline_metrics.get('latency_p95', 1)

        status = 'healthy'
        needs_retraining = False

        if accuracy_drift > drift_threshold:
            status = 'drift_detected'
            needs_retraining = True
            self._trigger_alert({
                'type': 'accuracy_drift',
                'severity': 'warning',
                'message': f'Accuracy drifted by {accuracy_drift:.2%} (threshold: {drift_threshold:.2%})',
                'metric': 'accuracy_drift',
                'value': accuracy_drift,
                'threshold': drift_threshold,
                'action': 'retraining_recommended'
            })

        report = {
            'status': status,
            'accuracy_drift': accuracy_drift,
            'latency_drift': latency_drift,
            'needs_retraining': needs_retraining,
            'threshold': drift_threshold
        }

        logger.info(f"Drift: Accuracy={accuracy_drift:.2%}, Latency={latency_drift:.2%}")

        return report

    def check_stale_metadata(self, chunks_metadata: List[Dict]) -> Dict:
        """
        Check for stale metadata (>30 days old).

        Args:
            chunks_metadata: List of chunk metadata dicts

        Returns:
            Staleness report
        """
        logger.info(f"Checking staleness for {len(chunks_metadata)} chunks")

        threshold_days = 30
        cutoff_date = datetime.now() - timedelta(days=threshold_days)

        stale_count = 0
        for chunk in chunks_metadata:
            publish_date_str = chunk.get('metadata', {}).get('publish_date', '')
            if publish_date_str:
                try:
                    publish_date = datetime.fromisoformat(publish_date_str.replace('Z', '+00:00'))
                    if publish_date < cutoff_date:
                        stale_count += 1
                except:
                    pass  # Skip invalid dates

        total = len(chunks_metadata)
        staleness_pct = stale_count / total if total > 0 else 0.0

        staleness_threshold = self.alerts_config.get('thresholds', {}).get('staleness_warning', 0.03)

        if PROMETHEUS_AVAILABLE:
            self.metrics.chunk_staleness.set(staleness_pct)
            self.metrics.active_chunks.set(total)

        status = 'healthy'
        if staleness_pct > staleness_threshold:
            status = 'warning'
            self._trigger_alert({
                'type': 'staleness_warning',
                'severity': 'warning',
                'message': f'{staleness_pct:.2%} of chunks are stale (>{threshold_days} days)',
                'metric': 'chunk_staleness',
                'value': staleness_pct,
                'threshold': staleness_threshold
            })

        report = {
            'status': status,
            'total_chunks': total,
            'stale_chunks': stale_count,
            'staleness_percentage': staleness_pct,
            'threshold': staleness_threshold,
            'threshold_days': threshold_days
        }

        logger.info(f"Staleness: {stale_count}/{total} ({staleness_pct:.2%})")

        return report

    def _trigger_alert(self, alert: Dict):
        """
        Trigger an alert through configured channels.

        Args:
            alert: Alert dictionary with type, severity, message, etc.
        """
        alert['timestamp'] = datetime.now().isoformat()
        alert['id'] = f"{alert['type']}_{int(time.time())}"

        self.active_alerts.append(alert)
        self.alert_history.append(alert)

        logger.warning(f"⚠️  ALERT [{alert['severity'].upper()}]: {alert['message']}")

        # Send to configured channels
        channels = self.alerts_config.get('channels', {})

        if channels.get('slack', {}).get('enabled'):
            self._send_slack_alert(alert)

        if channels.get('pagerduty', {}).get('enabled'):
            self._send_pagerduty_alert(alert)

        if channels.get('email', {}).get('enabled'):
            self._send_email_alert(alert)

    def _send_slack_alert(self, alert: Dict):
        """Send alert to Slack (placeholder)."""
        logger.info(f"Would send to Slack: {alert['message']}")
        # TODO: Implement Slack webhook integration

    def _send_pagerduty_alert(self, alert: Dict):
        """Send alert to PagerDuty (placeholder)."""
        logger.info(f"Would send to PagerDuty: {alert['message']}")
        # TODO: Implement PagerDuty API integration

    def _send_email_alert(self, alert: Dict):
        """Send alert via email (placeholder)."""
        logger.info(f"Would send email: {alert['message']}")
        # TODO: Implement SMTP email integration

    def get_active_alerts(self) -> List[Dict]:
        """Get list of active alerts."""
        return self.active_alerts

    def clear_alert(self, alert_id: str):
        """Clear an active alert."""
        self.active_alerts = [a for a in self.active_alerts if a['id'] != alert_id]

    def run_monitoring(self, chunks_metadata: Optional[List[Dict]] = None) -> Dict:
        """
        Execute complete monitoring cycle.

        Args:
            chunks_metadata: Optional chunks metadata for staleness check

        Returns:
            Monitoring summary report
        """
        logger.info("=" * 60)
        logger.info("Starting Monitoring Cycle")
        logger.info("=" * 60)

        # Collect all metrics
        latency_report = self.collect_latency_metrics()
        accuracy_report = self.collect_accuracy_metrics()

        staleness_report = {}
        if chunks_metadata:
            staleness_report = self.check_stale_metadata(chunks_metadata)

        # Check for drift (placeholder - needs baseline)
        drift_report = {'status': 'skipped', 'reason': 'no_baseline'}

        # Overall system health
        statuses = [
            latency_report.get('status'),
            accuracy_report.get('status'),
            staleness_report.get('status', 'unknown')
        ]

        if 'critical' in statuses:
            overall_status = 'CRITICAL'
        elif 'warning' in statuses:
            overall_status = 'WARNING'
        else:
            overall_status = 'HEALTHY'

        report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status,
            'latency': latency_report,
            'accuracy': accuracy_report,
            'staleness': staleness_report,
            'drift': drift_report,
            'active_alerts': len(self.active_alerts),
            'alerts': self.get_active_alerts()
        }

        logger.info("=" * 60)
        logger.info(f"Monitoring Complete: {overall_status}")
        logger.info("=" * 60)

        return report


def main():
    """Main entry point for Monitoring Agent."""
    logger.info("Monitoring Agent - System Health & Metrics Tracking")

    monitor = MonitoringAgent(
        alerts_config="./configs/alerts/alerts.yml",
        metrics_port=8000,
        enable_prometheus=False  # Set to True for Prometheus export
    )

    # Simulate some metrics for demo
    monitor.metrics.record_query('retail', 'success', 0.234)
    monitor.metrics.record_query('retail', 'success', 0.456)
    monitor.metrics.record_query('advisor', 'success', 0.123)
    monitor.metrics.record_accuracy(0.87)
    monitor.metrics.record_accuracy(0.92)

    report = monitor.run_monitoring()

    logger.info(f"System Status: {report['overall_status']}")
    logger.info(f"Active Alerts: {report['active_alerts']}")


if __name__ == "__main__":
    main()
