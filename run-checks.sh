#!/bin/bash
set -e

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

exit_code=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Python: Formatting (ruff format)${NC}"
echo -e "${BLUE}========================================${NC}"
if ruff format .; then
    echo -e "${GREEN}Python formatting: OK${NC}"
else
    echo -e "${RED}Python formatting: FAILED${NC}"
    exit_code=1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Python: Linting (ruff check)${NC}"
echo -e "${BLUE}========================================${NC}"
if ruff check . --fix; then
    echo -e "${GREEN}Python linting: OK${NC}"
else
    echo -e "${YELLOW}Python linting: issues found (see above)${NC}"
    exit_code=1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  JavaScript: Linting (eslint)${NC}"
echo -e "${BLUE}========================================${NC}"
if npx eslint web/static/js/ --fix; then
    echo -e "${GREEN}JavaScript linting: OK${NC}"
else
    echo -e "${YELLOW}JavaScript linting: issues found (see above)${NC}"
    exit_code=1
fi

echo ""
if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  All checks passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  Some checks have issues. See above.${NC}"
    echo -e "${RED}========================================${NC}"
fi

exit $exit_code
