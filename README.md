# 🎙️ Dictator (Whisperer) - Professional AI Voice Dictation

![Dictator V3 Overlay](sound-8825_256.gif)

**Dictator** is a high-performance, privacy-focused offline speech-to-text utility for Linux. Built with **GTK4**, **LibAdwaita**, and **faster-whisper**, it provides a seamless "Hold-to-Talk" experience that transcribes your voice in real-time and injects the text directly into any active application.

Version **3.1.0** introduces the "Manual Crank" animation engine and a clean, pulsing neon aesthetic.

---

## 🚀 The V3 Experience

Dictator is designed for users who want the speed of AI transcription without the overhead of cloud-based services. It sits silently in your tray or background until you need it.

- **Non-Intrusive Overlay**: A beautiful, floating GIF appears at the bottom of your screen during recording. It is a "ghost" window—it never steals focus, so you can keep typing while the Dictator listens.
- **Pulsing Neon Glow**: The recording indicator features a CSS-driven pulsing aura that makes the UI feel alive and responsive.
- **Global Precision**: Uses `pynput` for cross-application hotkey detection and `sounddevice` for low-latency audio capture.

---

## ✨ Features

### 🎙️ Core Dictation
- **Hold-to-Talk (F8)**: The most intuitive way to dictate. Hold to record, release to paste.
- **Auto-Injection**: Transcribed text is automatically typed into your current cursor position using virtual keyboard emulation.
- **Advanced Noise Handling**: Optimized for various environments using Whisper's robust AI models.

### 🎨 Visual & UI
- **Glassmorphic Main Dashboard**: A sleek, semi-transparent interface following modern design trends.
- **Dynamic Accent Colors**: Choose your "Neon Theme" (Lime, Blue, Pink, etc.) via the preferences.
- **GIF Customization**: Upload your own recording animations.
- **"Manual Crank" Animation**: Custom engine ensures GIFs play perfectly on all Linux distributions by manually advancing every frame at the hardware level.

### ⚙️ Power Features
- **Clipboard History Monitoring**: Keep track of everything you copy with a built-in history manager.
- **Model Selection**: Switch between `tiny`, `base`, and `small` models depending on your hardware (CPU/GPU acceleration supported via CTranslate2).
- **Auto-Start**: Integrated scripts to ensure Dictator is ready as soon as you log in.

---

## 🛠️ Technical Architecture

### 1. The "Manual Crank" Engine
GTK4 sometimes struggles with certain GIF formats in non-standard window types. Dictator V3 solves this by using a `GdkPixbuf.PixbufAnimation` iterator. We manually "crank" the frames using `GLib.timeout_add`, ensuring constant frame rates and zero freezes.

### 2. Focus Stealing Prevention
Overlay windows often interrupt workflows by stealing keyboard focus. Dictator implements a strict "Non-Focusable" policy:
- `set_can_focus(False)`
- `set_focusable(False)`
- `set_can_target(False)`
This ensures your active document stays active while the overlay glows below.

### 3. Glassmorphic CSS Engine
Custom CSS tokens are used to create the futuristic look:
```css
.glass-view {
    background: rgba(30, 30, 30, 0.7);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
}
```

---

## 📥 Installation

### Prerequisites
- **Python 3.10+**
- **System Libraries**:
  ```bash
  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0 portaudio19-dev ffmpeg
  ```

### Automated Setup
1. Clone the repo:
   ```bash
   git clone https://github.com/Akubrecah/whisperer.git
   cd whisperer
   ```
2. Run the main installer (handles virtual environments and requirements):
   ```bash
   bash install.sh
   ```
3. Enable Autostart (Optional):
   ```bash
   bash setup_autostart.sh
   ```

---

## 🖥️ Usage Guide

1. **Launch**: Open Dictator from your "Office" or "Utilities" menu.
2. **Setup**: Go to **Preferences** to select your AI model (Tiny is fastest, Base is more accurate).
3. **Dictate**: Simply hold your hotkey (Default: `F8`). Speak clearly.
4. **Release**: Let go of the key. Wait ~1 second for the AI to process. The text will appear instantly.

---

## 👨‍💻 Development

Want to contribute or customize?
- **Styles**: Check `style.css` for the design system.
- **Logic**: `main.py` contains the GTK application and the `TranscriptionWorker` thread.
- **Assets**: Place your GIFs in the root or select them via the UI.

### Requirements
- `faster-whisper`
- `sounddevice`
- `pynput`
- `PyGObject`

---

## 📜 Changelog

### Version 3.3.0 - "The Persistent Release"
- **Integrated Settings**: Settings moved from a popup window to a dedicated dashboard page.
- **Pinning System**: History items and clipboards can now be pinned to stay forever.
- **Auto-Expiry**: Unpinned items automatically disappear after 1 hour (configurable soon).
- **Drag & Drop Reordering**: Reorder your history and clipboards by dragging them.
- **Unlimited History**: Removed the 10-item limit for pinned content.

### Version 3.2.0
- **Dashboard Refresh**: Added clipboard history directly to the main main dashboard view.
- **Release-to-Paste**: Refined "Hold-to-Talk" logic to wait for full final transcription before pasting.
- **Split Layout**: Side-by-side view for recording orb and recent clips.

### Version 3.1.2
- **Stability**: Suppressed `GError` spam when copying non-text content (images/files) to clipboard.

### Version 3.1.1
- **Aesthetics**: Shifted GIF colors to pure white and changed neon pulse to Cyber Red.

### Version 3.1.0 - "The Radiant Release"
- **"Manual Crank" Engine**: Performance-optimized GIF engine for zero-freeze animation.
- **Neon Pulse**: CSS-driven glow effects for the recording overlay.
- **Focus Protection**: Non-intrusive windows that don't steal user focus.

### Version 3.0.0
- **Initial Whisper V3**: Complete migration to `faster-whisper` and GTK4.

---

## 📄 License & Credits
Developed with ❤️ by **Akubrecah**.
Powered by OpenAI's Whisper models and the LibAdwaita team.

*Version 3.3.0 - Current Stable Development*
