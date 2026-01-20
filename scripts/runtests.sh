#!/bin/bash
# runtests.sh - Run all AI_OS tests
# Usage: ./runtests.sh [--unit] [--coherence] [--adversarial] [--all]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default backend port (change if needed)
NOLA_BACKEND="http://localhost:8000"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

print_header() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
    echo ""
}

check_backend() {
    echo -e "${BLUE}Checking if Nola backend is running...${NC}"
    if curl -s "$NOLA_BACKEND/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is running at $NOLA_BACKEND${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Backend not running. Starting it...${NC}"
        python3 Nola/react-chat-app/backend/main.py &
        BACKEND_PID=$!
        sleep 3
        if curl -s "$NOLA_BACKEND/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
            return 0
        else
            echo -e "${RED}❌ Failed to start backend${NC}"
            return 1
        fi
    fi
}

check_ollama() {
    echo -e "${BLUE}Checking if Ollama is running...${NC}"
    if curl -s "http://localhost:11434/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama is running${NC}"
        return 0
    else
        echo -e "${RED}❌ Ollama not running. Please start it first.${NC}"
        return 1
    fi
}

run_unit_tests() {
    print_header "🧪 UNIT TESTS"
    echo -e "${BLUE}Running pytest...${NC}"
    echo ""
    
    if python3 -m pytest tests/ -v --tb=short; then
        echo ""
        echo -e "${GREEN}✅ Unit tests passed${NC}"
        return 0
    else
        echo ""
        echo -e "${RED}❌ Unit tests failed${NC}"
        return 1
    fi
}

run_coherence_test() {
    print_header "🎯 COHERENCE TEST (Nola vs Raw LLM)"
    echo -e "${BLUE}Testing: Structure beats scale hypothesis${NC}"
    echo -e "${BLUE}Nola (7B + HEA) vs Raw 20B model${NC}"
    echo ""
    
    python3 -c "
import sys
sys.path.insert(0, '.')
import eval.coherence_test as ct
ct.NOLA_BACKEND = '$NOLA_BACKEND'
ct.run_coherence_test()
"
    
    echo ""
    echo -e "${GREEN}✅ Coherence test complete - transcript saved to eval/transcripts/${NC}"
}

run_adversarial_test() {
    print_header "⚔️  ADVERSARIAL IDENTITY BATTLE"
    echo -e "${BLUE}Testing: Identity persistence under attack${NC}"
    echo -e "${BLUE}50 turns of escalating adversarial pressure${NC}"
    echo ""
    
    TURNS=${1:-50}
    
    python3 -c "
import sys
sys.path.insert(0, '.')
import eval.identity_battle as ib
ib.NOLA_BACKEND = '$NOLA_BACKEND'
ib.run_identity_battle($TURNS)
"
    
    echo ""
    echo -e "${GREEN}✅ Adversarial test complete - transcript saved to eval/transcripts/${NC}"
}

show_help() {
    echo "Usage: ./runtests.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --unit          Run unit tests only"
    echo "  --coherence     Run coherence test only"
    echo "  --adversarial   Run adversarial identity battle only"
    echo "  --adversarial N Run adversarial test with N turns (default: 50)"
    echo "  --eval          Run both eval tests (coherence + adversarial)"
    echo "  --all           Run everything (unit + coherence + adversarial)"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./runtests.sh --unit              # Just unit tests"
    echo "  ./runtests.sh --eval              # Coherence + adversarial"
    echo "  ./runtests.sh --adversarial 20   # Quick 20-turn battle"
    echo "  ./runtests.sh --all               # Everything"
    echo ""
    echo "Environment:"
    echo "  NOLA_BACKEND    Backend URL (default: http://localhost:8000)"
}

# Parse arguments
RUN_UNIT=false
RUN_COHERENCE=false
RUN_ADVERSARIAL=false
ADVERSARIAL_TURNS=50

if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            RUN_UNIT=true
            shift
            ;;
        --coherence)
            RUN_COHERENCE=true
            shift
            ;;
        --adversarial)
            RUN_ADVERSARIAL=true
            shift
            # Check if next arg is a number
            if [[ $1 =~ ^[0-9]+$ ]]; then
                ADVERSARIAL_TURNS=$1
                shift
            fi
            ;;
        --eval)
            RUN_COHERENCE=true
            RUN_ADVERSARIAL=true
            shift
            ;;
        --all)
            RUN_UNIT=true
            RUN_COHERENCE=true
            RUN_ADVERSARIAL=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Override backend URL from env if set
if [ -n "$NOLA_BACKEND_URL" ]; then
    NOLA_BACKEND="$NOLA_BACKEND_URL"
fi

print_header "🧠 AI_OS Test Runner"

# Run selected tests
FAILED=0

if $RUN_UNIT; then
    run_unit_tests || FAILED=1
fi

if $RUN_COHERENCE || $RUN_ADVERSARIAL; then
    check_ollama || exit 1
    check_backend || exit 1
fi

if $RUN_COHERENCE; then
    run_coherence_test || FAILED=1
fi

if $RUN_ADVERSARIAL; then
    run_adversarial_test $ADVERSARIAL_TURNS || FAILED=1
fi

# Summary
print_header "📊 TEST SUMMARY"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests completed successfully${NC}"
else
    echo -e "${RED}❌ Some tests failed${NC}"
fi

echo ""
echo -e "${BLUE}Transcripts saved to: eval/transcripts/${NC}"
echo ""

exit $FAILED
