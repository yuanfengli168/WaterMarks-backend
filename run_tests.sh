#!/bin/bash
# Setup and Run Tests
# This script sets up the environment and runs tests

echo "🧪 WaterMarks Backend - Test Runner"
echo "===================================="
echo ""

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
    pip install -r requirements-test.txt
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "📥 Installing test dependencies..."
    pip install -r requirements-test.txt
fi

# Check if test PDFs exist
if [ ! -d "tests/test_data" ] || [ -z "$(ls -A tests/test_data 2>/dev/null)" ]; then
    echo "📄 Generating test PDF files..."
    python3 tests/generate_test_pdfs.py
fi

# Run tests
echo ""
echo "▶️  Running tests..."
echo ""
pytest "$@"
