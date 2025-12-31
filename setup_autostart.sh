#!/bin/bash

# Dictator Autostart Setup
echo "⚙️ Configuring Autostart for Dictator..."

DESKTOP_FILE="$HOME/.local/share/applications/dictator.desktop"
AUTOSTART_DIR="$HOME/.config/autostart"

if [ ! -f "$DESKTOP_FILE" ]; then
    echo "❌ Error: dictator.desktop not found. Please run install.sh first."
    exit 1
fi

mkdir -p "$AUTOSTART_DIR"
cp "$DESKTOP_FILE" "$AUTOSTART_DIR/"

echo "🚀 Autostart enabled! Dictator will launch on next login."
