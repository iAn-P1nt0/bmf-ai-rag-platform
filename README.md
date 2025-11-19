# BMF AI RAG Platform

BMF AI-powered RAG (Retrieval-Augmented Generation) platform for intelligent asset management query assistance.

## Overview

The BMF AI RAG Platform is an end-to-end system that:
- Scrapes and ingests content from BMF
- Processes documents into searchable chunks with rich metadata
- Provides a Claude-powered copilot for answering fund queries with grounded citations
- Maintains compliance with regulatory requirements and disclaimers

## Architecture

Based on two core playbooks:
- **CLAUDE.md**: RAG copilot behavior, reasoning patterns, and response guidelines
- **AGENTS.md**: Data pipeline architecture with 7 specialized agents

### Agent Roster

| Agent | Schedule | Purpose |
|-------|----------|---------|
| Discovery | Daily 00:30 IST | Track site structure changes, maintain URL manifest |
| Scraper | Daily 02:00 IST | Render and capture web pages with Playwright |
| Document Harvester | Daily 02:30 IST | Download PDFs, factsheets, compliance docs |
| Parser | Daily 03:00 IST | Convert HTML/PDF to structured Markdown/JSON |
| Chunk Orchestrator | Daily 03:30 IST | Create semantic chunks, push to vector store |
| Validator | Daily 04:00 IST | Run regression tests, verify quality metrics |
| Monitoring | 24/7 | Track latency, accuracy, drift; alert on issues |

### Claude RAG Copilot

5-step reasoning pattern:
1. **Clarify**: Detect investor type, disambiguate queries
2. **Retrieve**: Fetch top-6 hybrid-scored chunks from AgentSet
3. **Ground**: Draft response with citations and key figures
4. **Validate**: Apply compliance rules, add disclaimers
5. **Deliver**: Return concise answer with confidence score

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone <repo-url>
cd bmf-ai-rag-platform

# Install dependencies
pip install -r requirements.txt

# Initialize platform
python manage.py init
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials:
# - ANTHROPIC_API_KEY (for Claude)
# - AGENTSET_API_KEY (for vector store)
# - AWS credentials (for S3 storage)
```

### 3. Run Pipeline

```bash
# Run full pipeline
python manage.py pipeline

# Or run individual agents
python manage.py discovery
python manage.py scrape --section funds
python manage.py harvest
```

### 4. Query the Copilot

```bash
# Interactive query
python manage.py query "What is the NAV of Bandhan Core Equity Fund?"

# Or use Python API
from src.rag_copilot.claude_rag_copilot import ClaudeRAGCopilot

copilot = ClaudeRAGCopilot()
response = copilot.query("Show me latest factsheet for debt funds")
print(response.answer)
```

## Configuration Files

### Site Map (`configs/site_map/SITE_MAP.json`)
Defines target sections, URL patterns, and scraping rules for bmf

### Chunking Policy (`configs/chunking/chunking.yml`)
- Max 1,200 tokens per chunk
- 20-30% overlap
- Structure-aware splitting (DOM elements, PDF sections)
- Table preservation

### Metadata Schema (`configs/metadata_schema/metadata_schema.json`)
Required fields per chunk:
- fund_name, category, risk_profile
- doc_type, publish_date
- crawler_version, checksum
- source_url

### Alert Rules (`configs/alerts/alerts.yml`)
KPI thresholds:
- Retrieval accuracy: 80-85%
- Latency: <500ms (target), <900ms (critical)
- Coverage: 15k-20k active chunks
- Stale metadata: <3%

## Management CLI

```bash
# Platform management
python manage.py status          # Show platform status
python manage.py validate        # Run test suite
python manage.py pipeline        # Execute full pipeline

# Individual agents
python manage.py discovery       # Discover URLs
python manage.py scrape          # Scrape web pages
python manage.py harvest         # Download documents

# Query copilot
python manage.py query "your question here"
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run regression tests (20 prompts)
pytest tests/regression/test_rag_regression.py -v

# Check citation match rate (target: >90%)
pytest tests/regression/test_rag_regression.py::test_citation_match_rate

# Check retrieval accuracy (target: 80-85%)
pytest tests/regression/test_rag_regression.py::test_retrieval_accuracy_target
```

## Airflow Pipeline

```bash
# Start Airflow
airflow standalone

# Access UI at http://localhost:8080
# Enable DAG: bmf_rag_pipeline

# Manual trigger
airflow dags trigger bmf_rag_pipeline
```

## Key Features

### Compliance & Safety
- Never hallucinates - all responses grounded in retrieved evidence
- Refuses queries below 0.6 confidence threshold
- Disclaimers for past performance, risk disclosures
- Rejects personalized investment advice

### Performance Targets
- Latency: <500ms (P95), <900ms worst case
- Retrieval accuracy: 80-85%
- Citation match: >90% in regression tests
- Coverage: 15k-20k active chunks

### Data Quality
- SHA-256 checksums for deduplication
- Metadata completeness validation (>90%)
- Daily automated regression testing
- Weekly human spot checks

## Project Structure

```
bmf-ai-rag-platform/
├── agents/                  # 7 specialized agents
│   ├── discovery/          # URL discovery
│   ├── scraper/            # Web scraping
│   ├── document_harvester/ # PDF downloads
│   ├── parser/             # Content parsing
│   ├── chunk_orchestrator/ # Chunking & ingestion
│   ├── validator/          # Quality validation
│   └── monitoring/         # Metrics & alerts
├── src/
│   └── rag_copilot/        # Claude RAG copilot
├── configs/                # Configuration files
│   ├── site_map/          # URL patterns
│   ├── chunking/          # Chunking rules
│   ├── metadata_schema/   # Metadata definitions
│   └── alerts/            # Alert thresholds
├── airflow_dags/          # Airflow pipeline DAGs
├── tests/                 # Test suite
│   ├── unit/
│   ├── integration/
│   └── regression/        # 20 regression prompts
├── data/                  # Data storage
│   ├── raw/              # HTML & PDF
│   ├── processed/        # Parsed content
│   └── cache/            # SQLite diff DB
├── manage.py             # CLI management tool
├── requirements.txt      # Python dependencies
├── CLAUDE.md            # Copilot playbook
└── AGENTS.md            # Pipeline architecture
```

## Next Steps

1. **Complete Remaining Agents**:
   - Parser Agent (Unstructured.io integration)
   - Chunk Orchestrator (AgentSet SDK)
   - Validator Agent (Great Expectations)
   - Monitoring Agent (Prometheus/Grafana)

2. **Integration**:
   - Connect to actual AgentSet vector store
   - Set up S3 buckets for storage
   - Configure Azure AI for Claude hosting

3. **Deployment**:
   - Set up Airflow on production infrastructure
   - Configure monitoring dashboards
   - Enable PagerDuty/Slack alerts

4. **Validation**:
   - Populate index with real BMF data
   - Run full regression suite
   - Conduct weekly human evaluations

## Documentation

- **CLAUDE.md**: Complete RAG copilot specifications
- **AGENTS.md**: Pipeline architecture and agent details
- **configs/**: Detailed configuration schemas
- **tests/**: Test suite documentation

## License

Proprietary Do Not Copy
