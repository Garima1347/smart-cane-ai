#!/usr/bin/env bash
# One-time setup for Raspberry Pi 5 (deployment device).
# Tested against Raspberry Pi OS (Bookworm, 64-bit).
set -e

echo "=== Smart Cane — Raspberry Pi 5 setup ==="

echo "--> Updating apt and installing system packages..."
sudo apt update
sudo apt install -y \
    python3-venv python3-pip python3-opencv \
    espeak-ng \
    libatlas-base-dev \
    python3-picamera2 \
    python3-lgpio

# NOTE: python3-picamera2 and python3-lgpio are installed via apt (not pip)
# because they need to link against system libraries. We create the venv
# with --system-site-packages so it can see these apt-installed packages.

echo "--> Creating Python virtual environment (with access to system packages)..."
python3 -m venv venv --system-site-packages
source venv/bin/activate

echo "--> Upgrading pip..."
pip install --upgrade pip

echo "--> Installing Python dependencies..."
pip install -r requirements.txt

echo "--> Installing GPIO + camera Python packages..."
pip install gpiozero lgpio

echo ""
echo "=== Setup complete ==="
echo "Run the app with:"
echo "    source venv/bin/activate"
echo "    python main.py"
echo ""
echo "Wiring reminder (HC-SR04 -> Pi 5 GPIO, default pins in config.yaml):"
echo "  VCC  -> 5V (pin 2)"
echo "  GND  -> GND (pin 6)"
echo "  TRIG -> GPIO23 (pin 16)"
echo "  ECHO -> GPIO24 (pin 18) via a voltage divider (5V -> 3.3V!)"
echo ""
echo "If you get a 'permission denied' GPIO error, add your user to the gpio group:"
echo "    sudo usermod -aG gpio \$USER   (then log out and back in)"
