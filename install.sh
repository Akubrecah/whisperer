#!/bin/bash

# Dictator Installer for Kali Linux
echo "🚀 Starting Dictator Installation..."

# 1. Update and install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    libadwaita-1-0 \
    python3-venv \
    portaudio19-dev \
    ffmpeg \
    libgirepository1.0-dev

# 2. Setup Virtual Environment
echo "🐍 Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv --system-site-packages venv
fi

# 3. Install Python dependencies
echo "📥 Installing Python packages..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 4. Create Desktop Entry
echo "🖥️ Creating desktop entry..."
APP_PATH=$(pwd)
PYTHON_PATH="$APP_PATH/venv/bin/python"
MAIN_SCRIPT="$APP_PATH/main.py"

DESKTOP_ENTRY="[Desktop Entry]
Name=Dictator
Comment=Futuristic Live Speech-to-Text
Exec=$PYTHON_PATH $MAIN_SCRIPT
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Utility;
Keywords=speech;text;dictation;"

mkdir -p ~/.local/share/applications/
echo "$DESKTOP_ENTRY" > ~/.local/share/applications/dictator.desktop

echo "✅ Installation complete! You can find 'Dictator' in your application menu."
echo "💡 To enable autostart, run: bash setup_autostart.sh"
