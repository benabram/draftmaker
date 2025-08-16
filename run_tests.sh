#!/bin/bash

# Run tests for the draftmaker project

echo "================================================"
echo "Running Draft Maker Test Suite"
echo "================================================"
echo ""

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run all tests with coverage
echo "Running all tests with coverage..."
python -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

# Check if tests passed
if [ $? -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "✅ All tests passed successfully!"
    echo "================================================"
    echo ""
    echo "Coverage report generated in htmlcov/index.html"
else
    echo ""
    echo "================================================"
    echo "❌ Some tests failed. Please review the output above."
    echo "================================================"
    exit 1
fi

# Optional: Run specific test categories
if [ "$1" == "--unit" ]; then
    echo ""
    echo "Running unit tests only..."
    python -m pytest tests/test_upc_processor.py tests/test_orchestrator.py -v
elif [ "$1" == "--integration" ]; then
    echo ""
    echo "Running integration tests only..."
    python -m pytest tests/test_integration.py -v
elif [ "$1" == "--quick" ]; then
    echo ""
    echo "Running quick tests (no coverage)..."
    python -m pytest tests/ -v -x
fi
