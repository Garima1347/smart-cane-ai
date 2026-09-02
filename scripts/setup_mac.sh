#!/usr/bin/env bash
# One-time setup for macOS (development machine).
set -e

echo "=== Smart Cane — macOS setup ==="

# Homebrew check (needed for portaudio, sometimes required by pyttsx3 deps)
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Install it from https://brew.sh first, then re-run this script."
    exit 1
fi

echo "--> Installing system dependencies (portaudio for audio)..."
brew install portaudio || true

echo "--> Creating Python virtual environment (venv)..."
python3 -m venv venv
source venv/bin/activate

echo "--> Upgrading pip..."
pip install --upgrade pip

echo "--> Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "=== Setup complete ==="
echo "Run the app with:"
echo "    source venv/bin/activate"
echo "    python main.py"
echo ""
echo "Tip: use --interactive-sensor to type distance values manually and test alerts,"
echo "since your Mac has no real ultrasonic sensor attached."
