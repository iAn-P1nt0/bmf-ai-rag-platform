"""
Airflow DAG for BMF RAG Pipeline
Orchestrates the 7 agents in sequence per AGENTS.md
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup
import os


default_args = {
    'owner': 'bmf-rag-team',
    'depends_on_past': False,
    'email': ['ops-alert@bmf.ai'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2)
}

dag = DAG(
    'bmf_rag_pipeline',
    default_args=default_args,
    description='End-to-end BMF RAG data pipeline',
    schedule_interval='0 0 * * *',  # Daily at midnight IST
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['bmf', 'rag', 'production']
)


def run_discovery_agent(**context):
    """Execute Discovery Agent."""
    from agents.discovery.discovery_agent import DiscoveryAgent

    config_path = os.getenv('SITE_MAP_CONFIG_PATH', './configs/site_map/SITE_MAP.json')
    agent = DiscoveryAgent(config_path)
    report = agent.run_discovery()

    # Push report to XCom for downstream tasks
    context['task_instance'].xcom_push(key='discovery_report', value=report)
    return report


def run_scraper_agent(**context):
    """Execute Scraper Agent."""
    import asyncio
    from agents.scraper.scraper_agent import ScraperAgent

    site_map_path = os.getenv('SITE_MAP_CONFIG_PATH', './configs/site_map/SITE_MAP.json')
    output_dir = os.getenv('SCRAPER_OUTPUT_DIR', './data/raw/html')
    s3_bucket = os.getenv('S3_BUCKET_RAW')

    agent = ScraperAgent(
        site_map_path=site_map_path,
        output_dir=output_dir,
        s3_bucket=s3_bucket,
        rate_limit_rps=2.0
    )

    report = asyncio.run(agent.scrape_all_sections())
    context['task_instance'].xcom_push(key='scraper_report', value=report)
    return report


def run_document_harvester(**context):
    """Execute Document Harvester."""
    from agents.document_harvester.harvester_agent import DocumentHarvester

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
    context['task_instance'].xcom_push(key='harvester_report', value=report)
    return report


def run_parser_agent(**context):
    """Execute Parser Agent."""
    from agents.parser.parser_agent import ParserAgent

    site_map_path = os.getenv('SITE_MAP_CONFIG_PATH', './configs/site_map/SITE_MAP.json')
    html_input_dir = os.getenv('SCRAPER_OUTPUT_DIR', './data/raw/html')
    pdf_input_dir = os.getenv('HARVESTER_OUTPUT_DIR', './data/raw/pdf')
    output_dir = os.getenv('PARSER_OUTPUT_DIR', './data/processed')

    agent = ParserAgent(
        html_input_dir=html_input_dir,
        pdf_input_dir=pdf_input_dir,
        output_dir=output_dir,
        site_map_path=site_map_path
    )

    report = agent.run_parser()
    context['task_instance'].xcom_push(key='parser_report', value=report)
    return report


def run_chunk_orchestrator(**context):
    """Execute Chunk Orchestrator."""
    from agents.chunk_orchestrator.chunk_agent import ChunkOrchestrator

    input_dir = os.getenv('PARSER_OUTPUT_DIR', './data/processed')
    chunking_config = os.getenv('CHUNKING_CONFIG_PATH', './configs/chunking/chunking.yml')
    metadata_schema = os.getenv('METADATA_SCHEMA_PATH', './configs/metadata_schema/metadata_schema.json')
    diff_db_path = os.getenv('SQLITE_DB_PATH', './data/cache/bmf_diff.db')

    orchestrator = ChunkOrchestrator(
        input_dir=input_dir,
        chunking_config_path=chunking_config,
        metadata_schema_path=metadata_schema,
        diff_db_path=diff_db_path
    )

    report = orchestrator.run_orchestrator()
    context['task_instance'].xcom_push(key='chunk_report', value=report)
    return report


def run_validator_agent(**context):
    """Execute Validator Agent."""
    # Implementation would go here
    # from agents.validator.validator_agent import ValidatorAgent
    # agent = ValidatorAgent(...)
    # report = agent.validate_pipeline()
    print("Validator Agent execution placeholder")
    return {'status': 'completed'}


def check_validation_results(**context):
    """Check validation results and decide whether to proceed."""
    validator_report = context['task_instance'].xcom_pull(
        task_ids='validator_agent',
        key='return_value'
    )

    # Check validation KPIs
    # - <90% chunks have mandatory metadata -> FAIL
    # - Retrieval eval <80% relevance -> FAIL
    # - Compliance docs missing disclaimers -> FAIL

    # For now, simple pass
    return True


def send_pipeline_report(**context):
    """Send pipeline completion report."""
    import json
    from loguru import logger

    # Gather all reports
    discovery_report = context['task_instance'].xcom_pull(
        task_ids='discovery_agent',
        key='discovery_report'
    )
    scraper_report = context['task_instance'].xcom_pull(
        task_ids='scraper_agent',
        key='scraper_report'
    )

    pipeline_report = {
        'pipeline_run_date': context['execution_date'].isoformat(),
        'status': 'success',
        'discovery': discovery_report,
        'scraper': scraper_report,
        'timestamp': datetime.utcnow().isoformat()
    }

    logger.info(f"Pipeline Report:\n{json.dumps(pipeline_report, indent=2)}")

    # In production, send email/slack notification
    return pipeline_report


# Task 1: Discovery Agent (00:30 IST)
discovery_task = PythonOperator(
    task_id='discovery_agent',
    python_callable=run_discovery_agent,
    dag=dag
)

# Task 2: Scraper Agent (02:00 IST)
scraper_task = PythonOperator(
    task_id='scraper_agent',
    python_callable=run_scraper_agent,
    dag=dag
)

# Task 3: Document Harvester (02:30 IST)
harvester_task = PythonOperator(
    task_id='document_harvester',
    python_callable=run_document_harvester,
    dag=dag
)

# Task 4: Parser Agent (03:00 IST)
parser_task = PythonOperator(
    task_id='parser_agent',
    python_callable=run_parser_agent,
    dag=dag
)

# Task 5: Chunk Orchestrator (03:30 IST)
chunker_task = PythonOperator(
    task_id='chunk_orchestrator',
    python_callable=run_chunk_orchestrator,
    dag=dag
)

# Task 6: Validator Agent (04:00 IST)
validator_task = PythonOperator(
    task_id='validator_agent',
    python_callable=run_validator_agent,
    dag=dag
)

# Task 7: Validation Check
validation_check_task = PythonOperator(
    task_id='check_validation',
    python_callable=check_validation_results,
    dag=dag
)

# Task 8: Report Generation
report_task = PythonOperator(
    task_id='send_pipeline_report',
    python_callable=send_pipeline_report,
    dag=dag
)

# Define task dependencies (sequential pipeline)
discovery_task >> scraper_task >> harvester_task >> parser_task >> chunker_task >> validator_task >> validation_check_task >> report_task

# Optional: Add monitoring task that runs in parallel
with TaskGroup('monitoring', dag=dag) as monitoring_group:
    monitor_latency = BashOperator(
        task_id='monitor_latency',
        bash_command='echo "Monitoring latency metrics..."'
    )

    monitor_accuracy = BashOperator(
        task_id='monitor_accuracy',
        bash_command='echo "Monitoring accuracy metrics..."'
    )

# Monitoring runs independently
[discovery_task, scraper_task, harvester_task, parser_task, chunker_task, validator_task] >> monitoring_group
