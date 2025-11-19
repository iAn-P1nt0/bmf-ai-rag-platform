# BMF RAG Platform - Setup Guide

Complete setup instructions for the Bandhan Mutual Fund AI RAG Platform.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Initial Setup](#initial-setup)
5. [Running the Platform](#running-the-platform)
6. [Testing](#testing)
7. [Deployment](#deployment)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software
- Python 3.10 or higher
- pip (Python package manager)
- Git
- Playwright (for web scraping)
- SQLite (for local caching)

### Optional (for production)
- Docker (for containerized deployment)
- Apache Airflow (for pipeline orchestration)
- Prometheus & Grafana (for monitoring)
- Redis (for distributed rate limiting)

### Cloud Services
- **Microsoft Azure AI** - For Claude 3.5 Sonnet hosting
- **AgentSet.ai** - For vector store and retrieval
- **AWS S3** - For raw and processed data storage
- **PagerDuty** (optional) - For alerting

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd bmf-ai-rag-platform
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install chromium
```

## Configuration

### 1. Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and configure the following:

```bash
# Azure Configuration
AZURE_OPENAI_ENDPOINT=https://your-foundry.azure.com
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=claude-3-5-sonnet

# AgentSet Configuration
AGENTSET_API_KEY=your-agentset-key
AGENTSET_INDEX_NAME=bmf-rag-v1
AGENTSET_API_URL=https://api.agentset.ai/v1

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-south-1
S3_BUCKET_RAW=bmf-rag-raw
S3_BUCKET_PROCESSED=bmf-rag-processed

# Scraping Configuration
SCRAPE_RATE_LIMIT=2
ENABLE_SCREENSHOTS=true

# Performance Thresholds
RETRIEVAL_CONFIDENCE_THRESHOLD=0.6
LATENCY_TARGET_MS=500
RETRIEVAL_ACCURACY_TARGET=0.80
```

### 2. Configuration Files

Configuration files are pre-configured in `configs/` directory:

- **SITE_MAP.json** - URL patterns and scraping rules
- **chunking.yml** - Chunking policy and rules
- **metadata_schema.json** - Chunk metadata schema
- **alerts.yml** - Alert thresholds and rules

Review and customize these files if needed.

## Initial Setup

### 1. Run Platform Initialization

```bash
python manage.py init
```

This will:
- Create necessary directories
- Copy `.env.example` to `.env` (if not exists)
- Install Playwright browsers
- Validate configuration files

### 2. Verify Configuration

```bash
python manage.py status
```

This shows:
- Data directory status
- Latest reports
- Platform health

## Running the Platform

### Discovery Agent

Discover URLs from bandhanmutual.com:

```bash
python manage.py discovery
```

Output:
- Updated `SITE_MAP.json` with discovered URLs
- Discovery report in `data/processed/`

### Scraper Agent

Scrape web pages:

```bash
# Scrape all sections
python manage.py scrape

# Scrape specific section
python manage.py scrape --section funds

# Limit URLs per section
python manage.py scrape --section funds --limit 10
```

Output:
- HTML files in `data/raw/html/`
- Screenshots (if enabled)
- Scraper report

### Document Harvester

Download documents (PDFs, factsheets):

```bash
python manage.py harvest
```

Output:
- PDF files in `data/raw/pdf/`
- Checksums database for deduplication
- Harvest report

### Full Pipeline

Run all agents in sequence:

```bash
python manage.py pipeline
```

Executes:
1. Discovery Agent
2. Scraper Agent
3. Document Harvester
4. Parser Agent (placeholder)
5. Chunk Orchestrator (placeholder)
6. Validator Agent (placeholder)
7. Monitoring Agent (placeholder)

### Query the RAG Copilot

```bash
# Interactive query
python manage.py query "What is the NAV of Bandhan Core Equity Fund?"

# Python API
python
>>> from src.rag_copilot.claude_rag_copilot import ClaudeRAGCopilot
>>> copilot = ClaudeRAGCopilot()
>>> response = copilot.query("Show me latest factsheet for debt funds")
>>> print(response.answer)
>>> print(f"Confidence: {response.confidence.value}")
>>> print(f"Citations: {len(response.citations)}")
```

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Regression Tests

20 prompts covering all site sections:

```bash
pytest tests/regression/test_rag_regression.py -v
```

### Specific Test Targets

```bash
# Citation match rate (target: >90%)
pytest tests/regression/test_rag_regression.py::test_citation_match_rate

# Retrieval accuracy (target: 80-85%)
pytest tests/regression/test_rag_regression.py::test_retrieval_accuracy_target

# Confidence threshold enforcement
pytest tests/regression/test_rag_regression.py::test_confidence_threshold_enforcement

# Personalized advice refusal
pytest tests/regression/test_rag_regression.py::test_personalized_advice_refusal
```

## Deployment

### Development Deployment

```bash
./scripts/deploy.sh development
```

### Production Deployment

```bash
./scripts/deploy.sh production
```

Production deployment includes:
- Airflow setup
- Database initialization
- Health checks
- Validation tests

### Airflow Setup (Production)

```bash
# Initialize Airflow database
airflow db init

# Create admin user
airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@bmf-rag.ai \
  --password admin

# Start scheduler
airflow scheduler -D

# Start webserver
airflow webserver -D

# Access UI at http://localhost:8080
# Enable DAG: bmf_rag_pipeline
```

### Docker Deployment (Optional)

```bash
# Build image
docker build -t bmf-rag-platform .

# Run container
docker run -d \
  --name bmf-rag \
  -p 8080:8080 \
  --env-file .env \
  bmf-rag-platform
```

## Troubleshooting

### Common Issues

#### 1. Playwright Installation Fails

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install -y \
  libnss3 \
  libnspr4 \
  libatk1.0-0 \
  libatk-bridge2.0-0 \
  libcups2 \
  libdrm2 \
  libdbus-1-3 \
  libxkbcommon0 \
  libatspi2.0-0 \
  libxcomposite1 \
  libxdamage1 \
  libxfixes3 \
  libxrandr2 \
  libgbm1 \
  libpango-1.0-0 \
  libcairo2 \
  libasound2

# Then reinstall Playwright
playwright install chromium
```

#### 2. API Key Errors

Verify `.env` file has correct credentials:

```bash
# Check if .env exists
ls -la .env

# Validate environment variables
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('ANTHROPIC_API_KEY:', 'SET' if os.getenv('ANTHROPIC_API_KEY') else 'MISSING')
print('AGENTSET_API_KEY:', 'SET' if os.getenv('AGENTSET_API_KEY') else 'MISSING')
"
```

#### 3. Import Errors

Ensure you're in the virtual environment and dependencies are installed:

```bash
# Activate venv
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

#### 4. Rate Limit Errors

Adjust rate limit in `.env`:

```bash
SCRAPE_RATE_LIMIT=1.0  # Reduce from 2.0 to 1.0
```

#### 5. AgentSet Connection Errors

Currently using mock data. To connect to real AgentSet:

1. Get API key from AgentSet.ai
2. Update `.env` with credentials
3. Modify `src/rag_copilot/claude_rag_copilot.py` to use real client

### Logs

Check logs for debugging:

```bash
# View recent logs
tail -f logs/*.log

# Search for errors
grep -r "ERROR" logs/

# View specific agent logs
grep "Discovery Agent" logs/*.log
```

### Getting Help

- **Documentation**: See README.md, CLAUDE.md, AGENTS.md
- **Issues**: Check docs/changelog.md for known issues
- **Contact**: ops-alert@bmf.ai

## Next Steps

After successful setup:

1. **Populate Data**:
   ```bash
   python manage.py discovery
   python manage.py scrape --section funds --limit 5
   python manage.py harvest
   ```

2. **Test Copilot**:
   ```bash
   python manage.py query "What is the NAV of Bandhan Core Equity Fund?"
   ```

3. **Run Validation**:
   ```bash
   python manage.py validate
   ```

4. **Set Up Monitoring** (production):
   - Configure Prometheus
   - Set up Grafana dashboards
   - Enable PagerDuty alerts

5. **Schedule Pipeline** (production):
   - Enable Airflow DAG
   - Configure cron schedule
   - Monitor first few runs

## Performance Optimization

### Caching

Enable local caching for frequently accessed chunks:

```bash
# Set in .env
SQLITE_DB_PATH=./data/cache/bmf_diff.db
```

### Parallel Processing

For large-scale scraping:

```python
# Modify scraper to use concurrent workers
# See agents/scraper/scraper_agent.py
```

### S3 Optimization

Enable S3 Transfer Acceleration for faster uploads:

```bash
# In AWS Console, enable Transfer Acceleration for buckets
# Update .env
S3_USE_ACCELERATE=true
```

## Security Best Practices

1. **Never commit `.env` file** - Already in `.gitignore`
2. **Rotate API keys regularly** - Update in Azure Key Vault
3. **Use IAM roles** - For AWS S3 access (instead of access keys)
4. **Enable MFA** - For production accounts
5. **Audit logs** - Review access logs weekly

## Maintenance

### Daily Tasks
- Monitor pipeline runs via Airflow UI
- Check alert notifications
- Review error logs

### Weekly Tasks
- Run regression tests manually
- Spot-check 30 random chunks
- Review performance metrics
- Update SITE_MAP if needed

### Monthly Tasks
- Backup data to cold storage
- Review and update configurations
- Security audit
- Performance optimization review

---

For detailed architecture information, see AGENTS.md and CLAUDE.md.
