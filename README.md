# 🎙️ Dictator (Whisperer) - AI-Powered Voice Dictation

![Dictator Logo](sound-8825_256.gif)

**Dictator** is a futuristic, offline speech-to-text tool for Linux, built with GTK4 and LibAdwaita. It uses the powerful `faster-whisper` AI model to provide lightning-fast, accurate transcriptions that are automatically pasted into your active application.

## ✨ Features (Version 2.1)

- **Hold-to-Talk**: Press and hold a global hotkey (Default: `F8`) to record.
- **Auto-Paste**: Releasing the hotkey instantly transcribes and pastes the text into your focused field.
- **Glassmorphic UI**: A stunning, modern interface with neon accents and a pulsing recording orb.
- **Recording Overlay**: A visual indicator (GIF/Image) pops up while you're recording, so you always know when the "Dictator" is listening.
- **Clipboard History**: Tracks your system clipboard changes with a dedicated history view.
- **Offline AI**: No data leaves your machine. Powered by `faster-whisper` (Tiny/Base models).
- **Customizable**: Change hotkeys, accent colors, and overlay images in the Preferences window.

## 🚀 Installation

### Prerequisites
- Python 3.10+
- GObject Introspection (for GTK4/Adwaita)
- PortAudio (for audio recording)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/Akubrecah/whisperer.git
   cd whisperer
   ```
2. Run the installation script:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
3. (Optional) Enable autostart:
   ```bash
   chmod +x setup_autostart.sh
   ./setup_autostart.sh
   ```

## 🛠️ Usage
- **Start the app**: Launch `Dictator` from your application menu or run `python main.py`.
- **Talk**: Hold `F8` and speak.
- **Finish**: Release `F8`. Your text will appear where your cursor was.
- **History**: Click the "History" button to see past transcriptions and clipboard history.

## 🎨 Technology Stack
- **AI**: `faster-whisper`
- **GUI**: GTK4 & LibAdwaita
- **Input**: `pynput`, `sounddevice`
- **Lang**: Python

---
Developed by **Akubrecah** | [Back to Top](#-dictator-whisperer---ai-powered-voice-dictation)
