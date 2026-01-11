#!/usr/bin/env bash
set -e

echo "📦 Setting up Python virtual environment for Little Life"

# Always run from project root
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Choose Python
PYTHON_BIN="${PYTHON_BIN:-python3.12}"

echo "🔎 Using Python: $PYTHON_BIN"

# Remove old venv if it exists
if [ -d ".venv" ]; then
    echo "🧹 Removing existing .venv"
    rm -rf .venv
fi

# Create venv
echo "🐍 Creating virtual environment"
$PYTHON_BIN -m venv .venv

# Activate venv
echo "⚡ Activating virtual environment"
source .venv/bin/activate

# Upgrade tooling
echo "⬆️  Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

# Install requirements
if [ -f "requirements.txt" ]; then
    echo "📥 Installing requirements"
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt not found"
fi

echo ""
echo "✅ Virtual environment ready"
echo "👉 To activate later: source .venv/bin/activate"
