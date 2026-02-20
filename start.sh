#!/bin/bash
# Startup script for WaterMarks Backend

echo "🚀 Starting WaterMarks Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✏️  Please edit .env with your configuration"
fi

# Create temp directories
echo "📁 Creating temporary directories..."
mkdir -p temp_files/{uploads,processing,outputs}

# Start the server
echo "✅ Starting server..."
echo "📍 Server will be available at http://localhost:8000"
echo "📖 API docs available at http://localhost:8000/docs"
echo ""

python app.py
