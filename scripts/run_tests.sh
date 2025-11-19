#!/bin/bash
# Comprehensive test runner for BMF RAG Platform

set -e  # Exit on error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}BMF RAG Platform - Test Suite${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Default test mode
TEST_MODE=${1:-"all"}

# Create logs directory
mkdir -p logs

# Function to run tests with reporting
run_test_suite() {
    local suite_name=$1
    local pytest_args=$2

    echo -e "${YELLOW}Running ${suite_name}...${NC}"

    if pytest ${pytest_args} --junitxml=logs/junit_${suite_name}.xml --html=logs/report_${suite_name}.html --self-contained-html; then
        echo -e "${GREEN}✓ ${suite_name} passed${NC}"
        return 0
    else
        echo -e "${RED}✗ ${suite_name} failed${NC}"
        return 1
    fi
}

# Track results
FAILED_SUITES=()

case "$TEST_MODE" in
    "unit")
        echo -e "${BLUE}Running Unit Tests Only${NC}"
        echo ""
        run_test_suite "unit_tests" "tests/unit/ -v -m unit" || FAILED_SUITES+=("unit")
        ;;

    "integration")
        echo -e "${BLUE}Running Integration Tests Only${NC}"
        echo ""
        run_test_suite "integration_tests" "tests/integration/ -v -m integration" || FAILED_SUITES+=("integration")
        ;;

    "regression")
        echo -e "${BLUE}Running Regression Tests Only${NC}"
        echo ""
        run_test_suite "regression_tests" "tests/regression/ -v -m regression" || FAILED_SUITES+=("regression")
        ;;

    "performance")
        echo -e "${BLUE}Running Performance Tests${NC}"
        echo ""
        run_test_suite "performance_tests" "tests/performance/ -v -m slow --benchmark-only" || FAILED_SUITES+=("performance")
        ;;

    "fast")
        echo -e "${BLUE}Running Fast Tests (excluding slow tests)${NC}"
        echo ""
        run_test_suite "fast_tests" "tests/ -v -m 'not slow'" || FAILED_SUITES+=("fast")
        ;;

    "coverage")
        echo -e "${BLUE}Running Tests with Coverage Report${NC}"
        echo ""
        pytest tests/ -v \
            --cov=agents \
            --cov=src \
            --cov-report=html:logs/coverage_html \
            --cov-report=term-missing \
            --cov-report=xml:logs/coverage.xml \
            --junitxml=logs/junit_coverage.xml

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Coverage tests passed${NC}"
            echo -e "${BLUE}Coverage report available at: logs/coverage_html/index.html${NC}"
        else
            echo -e "${RED}✗ Coverage tests failed${NC}"
            FAILED_SUITES+=("coverage")
        fi
        ;;

    "all")
        echo -e "${BLUE}Running All Test Suites${NC}"
        echo ""

        # 1. Unit Tests
        run_test_suite "unit_tests" "tests/unit/ -v -m unit" || FAILED_SUITES+=("unit")
        echo ""

        # 2. Integration Tests
        run_test_suite "integration_tests" "tests/integration/ -v -m integration" || FAILED_SUITES+=("integration")
        echo ""

        # 3. Regression Tests
        run_test_suite "regression_tests" "tests/regression/ -v -m regression" || FAILED_SUITES+=("regression")
        echo ""

        # 4. Performance Tests (if requested)
        if [ "${RUN_PERF:-false}" == "true" ]; then
            run_test_suite "performance_tests" "tests/performance/ -v -m slow" || FAILED_SUITES+=("performance")
            echo ""
        fi

        # 5. Generate Coverage Report
        echo -e "${YELLOW}Generating Coverage Report...${NC}"
        pytest tests/ -v \
            --cov=agents \
            --cov=src \
            --cov-report=html:logs/coverage_html \
            --cov-report=term-missing \
            --cov-report=xml:logs/coverage.xml \
            --quiet

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Coverage report generated${NC}"
            echo -e "${BLUE}View at: logs/coverage_html/index.html${NC}"
        fi
        ;;

    "ci")
        echo -e "${BLUE}Running CI/CD Test Suite${NC}"
        echo ""

        # Fast, essential tests for CI/CD
        pytest tests/ -v \
            -m "not slow and not requires_network and not requires_s3" \
            --junitxml=logs/junit_ci.xml \
            --cov=agents \
            --cov=src \
            --cov-report=xml:logs/coverage.xml \
            --cov-report=term

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ CI tests passed${NC}"
        else
            echo -e "${RED}✗ CI tests failed${NC}"
            FAILED_SUITES+=("ci")
        fi
        ;;

    *)
        echo -e "${RED}Unknown test mode: $TEST_MODE${NC}"
        echo ""
        echo "Usage: $0 [mode]"
        echo ""
        echo "Available modes:"
        echo "  all          - Run all test suites (default)"
        echo "  unit         - Run unit tests only"
        echo "  integration  - Run integration tests only"
        echo "  regression   - Run regression tests only"
        echo "  performance  - Run performance tests only"
        echo "  fast         - Run fast tests (exclude slow)"
        echo "  coverage     - Run all tests with coverage"
        echo "  ci           - Run CI/CD test suite"
        echo ""
        echo "Environment variables:"
        echo "  RUN_PERF=true  - Include performance tests in 'all' mode"
        exit 1
        ;;
esac

# Summary
echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}=========================================${NC}"

if [ ${#FAILED_SUITES[@]} -eq 0 ]; then
    echo -e "${GREEN}All test suites passed! ✓${NC}"
    echo ""
    echo "Test reports available in:"
    echo "  - logs/junit_*.xml (JUnit format)"
    echo "  - logs/report_*.html (HTML reports)"
    echo "  - logs/coverage_html/index.html (Coverage report)"
    exit 0
else
    echo -e "${RED}Some test suites failed: ${FAILED_SUITES[*]} ✗${NC}"
    echo ""
    echo "Check logs in the logs/ directory for details"
    exit 1
fi
