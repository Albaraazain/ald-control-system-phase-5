#!/bin/bash
# Setup the development environment

echo "🚀 Setting up ALD Control System Environment..."
echo ""

# Check Python version
python_version=$(python3 --version 2>/dev/null)
if [ $? -ne 0 ]; then
    echo "❌ Python 3 is not installed or not in PATH"
    exit 1
fi
echo "✅ Found: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "myenv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv myenv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Install/upgrade pip
echo "📦 Upgrading pip..."
./myenv/bin/pip install --upgrade pip

# Install requirements
echo "📦 Installing requirements..."
./myenv/bin/pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install requirements"
    exit 1
fi

echo ""
echo "✅ Environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Create a .env file with your Supabase credentials:"
echo "   SUPABASE_URL=your_supabase_url"
echo "   SUPABASE_KEY=your_supabase_key"
echo ""
echo "2. Use the startup scripts in the scripts/ directory:"
echo "   - ./scripts/start_main_service.sh (Main ALD control service)"
echo "   - ./scripts/doctor.sh (Diagnostics)"
echo ""
