# whisper-dictator-core

The core logic behind the **Whisperer Dictator** application. This package provides a high-level Python API for live transcription with `faster-whisper` and premium GTK4 transparent overlays.

## Features
- **WhisperRecorder**: Easy audio streaming and live transcription.
- **RecordingOverlay**: A truly transparent, click-through GTK4 window for floating HUDs/GIFs.
- **Optimized for CPU**: Uses `int8` quantization for fast performance on standard hardware.

## Installation
```bash
pip install whisper-dictator-core
```

## Usage

### Transcription
```python
from whisper_dictator_core import WhisperRecorder

def on_text(text):
    print(f"I heard: {text}")

recorder = WhisperRecorder(model_size="tiny", callback=on_text)
recorder.start()
# ... wait ...
recorder.stop()
```

### GTK4 Overlay
```python
from whisper_dictator_core import RecordingOverlay
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

app = Gtk.Application(application_id='com.example.App')

def on_activate(app):
    overlay = RecordingOverlay(application=app, image_path="anim.gif")
    overlay.show_overlay()

app.connect('activate', on_activate)
app.run(None)
```
