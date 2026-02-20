#!/bin/bash
# Quick Start Script for WaterMarks Backend

echo "🚀 WaterMarks Backend - Quick Start"
echo "===================================="
echo ""

# Step 1: Install dependencies
echo "📦 Step 1: Installing dependencies..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing main dependencies..."
pip install -r requirements.txt

echo "Installing test dependencies..."
pip install -r requirements-test.txt

echo "✅ Dependencies installed"
echo ""

# Step 2: Copy environment file
echo "⚙️  Step 2: Setting up environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ Created .env file"
else
    echo "ℹ️  .env file already exists"
fi
echo ""

# Step 3: Create directories
echo "📁 Step 3: Creating directories..."
mkdir -p temp_files/{uploads,processing,outputs}
echo "✅ Directories created"
echo ""

# Step 4: Generate test PDFs
echo "📄 Step 4: Generating test PDF files..."
python3 tests/generate_test_pdfs.py
echo ""

# Step 5: Instructions
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "==========="
echo ""
echo "1. Start the server:"
echo "   python3 app.py"
echo ""
echo "2. Run tests:"
echo "   pytest                          # All tests"
echo "   pytest tests/unit/              # Unit tests only"
echo "   pytest tests/integration/       # Integration tests only"
echo ""
echo "3. Manual testing:"
echo "   python3 tests/manual_test.py    # Interactive testing"
echo ""
echo "4. View API docs:"
echo "   http://localhost:8000/docs"
echo ""
echo "📖 See TESTING.md for detailed testing guide"
echo "📖 See API_DOCS.md for API documentation"
echo ""
