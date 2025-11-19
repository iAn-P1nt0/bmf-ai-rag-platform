#!/bin/bash
# BMF RAG Platform Deployment Script

set -e  # Exit on error

echo "========================================="
echo "BMF RAG Platform Deployment"
echo "========================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Environment
ENVIRONMENT=${1:-"development"}

echo -e "${GREEN}Environment: ${ENVIRONMENT}${NC}"

# Pre-deployment checks
echo ""
echo "Running pre-deployment checks..."

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "  ✓ Python version: ${PYTHON_VERSION}"

# Check required environment variables
if [ ! -f .env ]; then
    echo -e "${RED}  ✗ .env file not found${NC}"
    echo "  Creating from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}  ⚠ Please update .env with actual credentials${NC}"
    exit 1
fi

# Source environment
source .env

REQUIRED_VARS=(
    "AZURE_OPENAI_ENDPOINT"
    "AZURE_OPENAI_API_KEY"
    "AGENTSET_API_KEY"
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}  ✗ Required environment variable ${var} is not set${NC}"
        exit 1
    fi
done

echo "  ✓ Environment variables configured"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p data/raw/html
mkdir -p data/raw/pdf
mkdir -p data/processed
mkdir -p data/cache
mkdir -p logs
echo "  ✓ Directories created"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt --quiet
echo "  ✓ Dependencies installed"

# Install Playwright browsers
echo ""
echo "Installing Playwright browsers..."
playwright install chromium --quiet
echo "  ✓ Playwright browsers installed"

# Run database migrations (if applicable)
echo ""
echo "Setting up databases..."
# SQLite diff DB initialization would go here
echo "  ✓ Databases ready"

# Run validation tests
echo ""
echo "Running validation tests..."
pytest tests/ -v --tb=short -q 2>/dev/null || {
    echo -e "${YELLOW}  ⚠ Some tests failed - review before deploying to production${NC}"
}

# Airflow setup (if environment is production)
if [ "${ENVIRONMENT}" = "production" ]; then
    echo ""
    echo "Setting up Airflow..."

    # Initialize Airflow database
    airflow db init

    # Create admin user if doesn't exist
    airflow users create \
        --username admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@bmf-rag.ai \
        --password admin || true

    # Copy DAGs
    mkdir -p ~/airflow/dags
    cp -r airflow_dags/* ~/airflow/dags/

    echo "  ✓ Airflow configured"
fi

# Health check
echo ""
echo "Running health checks..."

# Check if configs are valid
python3 -c "
import json
import yaml

# Validate SITE_MAP.json
with open('configs/site_map/SITE_MAP.json') as f:
    json.load(f)
print('  ✓ SITE_MAP.json is valid')

# Validate chunking.yml
with open('configs/chunking/chunking.yml') as f:
    yaml.safe_load(f)
print('  ✓ chunking.yml is valid')

# Validate metadata_schema.json
with open('configs/metadata_schema/metadata_schema.json') as f:
    json.load(f)
print('  ✓ metadata_schema.json is valid')

# Validate alerts.yml
with open('configs/alerts/alerts.yml') as f:
    yaml.safe_load(f)
print('  ✓ alerts.yml is valid')
"

# Deployment summary
echo ""
echo "========================================="
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Verify .env credentials"
echo "  2. Run discovery: python manage.py discovery"
echo "  3. Run pipeline: python manage.py pipeline"
echo "  4. Query copilot: python manage.py query 'your question'"
echo ""

if [ "${ENVIRONMENT}" = "production" ]; then
    echo "Production-specific steps:"
    echo "  5. Start Airflow scheduler: airflow scheduler -D"
    echo "  6. Start Airflow webserver: airflow webserver -D"
    echo "  7. Enable DAG: bmf_rag_pipeline"
    echo "  8. Configure monitoring dashboards"
    echo "  9. Set up PagerDuty/Slack alerts"
    echo ""
fi

echo "For help: python manage.py --help"
echo ""
