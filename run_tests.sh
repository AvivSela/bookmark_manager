#!/bin/bash
# Centralized test runner for all services
# Runs all service tests sequentially

set -e  # Exit on first failure

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running all service tests...${NC}\n"

# Track failures
FAILED_SERVICES=()

# Run bookmark service tests
echo -e "${YELLOW}=== Running Bookmark Service Tests ===${NC}"
if (cd services/bookmark_service && ./run_tests.sh "$@"); then
    echo -e "${GREEN}✓ Bookmark Service tests passed${NC}\n"
else
    echo -e "${RED}✗ Bookmark Service tests failed${NC}\n"
    FAILED_SERVICES+=("bookmark_service")
fi

# Run enrichment service tests
echo -e "${YELLOW}=== Running Enrichment Service Tests ===${NC}"
if (cd services/enrichment_service && ./run_tests.sh "$@"); then
    echo -e "${GREEN}✓ Enrichment Service tests passed${NC}\n"
else
    echo -e "${RED}✗ Enrichment Service tests failed${NC}\n"
    FAILED_SERVICES+=("enrichment_service")
fi

# Summary
echo -e "${YELLOW}=== Test Summary ===${NC}"
if [ ${#FAILED_SERVICES[@]} -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Tests failed in: ${FAILED_SERVICES[*]}${NC}"
    exit 1
fi
