import os
import threading
import queue
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import gi

# Ensure we use GTK4 and LibAdwaita
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

class DictatorApp(Adw.Application):
    """
    The main application class for Dictator.
    """
    def __init__(self):
        super().__init__(application_id='com.example.Dictator',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        # Create the main window
        self.window = DictatorWindow(application=self)
        self.window.present()

class DictatorWindow(Adw.ApplicationWindow):
    """
    Main interface for the Dictator app with Live Transcription.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("Dictator - Live")
        self.set_default_size(700, 500)

        # State management
        self.recording = False
        self.audio_queue = queue.Queue()
        self.model = None
        self.full_text = ""
        
        # UI Setup
        self.setup_ui()

    def setup_ui(self):
        view_stack = Adw.ToolbarView()
        self.set_content(view_stack)

        header = Adw.HeaderBar()
        view_stack.add_top_bar(header)

        # Main Layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_all(24)
        view_stack.set_content(main_box)

        # Text area with scrolling
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(300)
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.add_css_class("view")
        scrolled.set_child(self.text_view)
        main_box.append(scrolled)

        # Controls
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        main_box.append(button_box)

        self.record_btn = Gtk.Button(label="Start Dictating")
        self.record_btn.add_css_class("suggested-action")
        self.record_btn.add_css_class("pill")
        self.record_btn.connect("clicked", self.on_record_toggled)
        button_box.append(self.record_btn)

        self.copy_btn = Gtk.Button(label="Copy Transcript")
        self.copy_btn.connect("clicked", self.on_copy_clicked)
        button_box.append(self.copy_btn)

        # Status Footer
        self.status_label = Gtk.Label(label="Select 'Start' to begin live transcription")
        self.status_label.add_css_class("caption")
        main_box.append(self.status_label)

    def on_record_toggled(self, btn):
        if not self.recording:
            self.start_live_session()
        else:
            self.stop_live_session()

    def start_live_session(self):
        self.recording = True
        self.record_btn.set_label("Stop")
        self.record_btn.remove_css_class("suggested-action")
        self.record_btn.add_css_class("destructive-action")
        self.status_label.set_label("Initializing capture...")

        # Reset states
        self.full_text = ""
        self.text_view.get_buffer().set_text("")
        while not self.audio_queue.empty():
            self.audio_queue.get()

        # Audio stream callback
        self.stream = sd.InputStream(samplerate=16000, channels=1, callback=self.audio_callback)
        self.stream.start()

        # Start transcription worker
        threading.Thread(target=self.transcription_worker, daemon=True).start()

    def stop_live_session(self):
        self.recording = False
        self.record_btn.set_label("Start Dictating")
        self.record_btn.remove_css_class("destructive-action")
        self.record_btn.add_css_class("suggested-action")
        self.status_label.set_label("Transcription halted.")
        
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()

    def audio_callback(self, indata, frames, time, status):
        """Streaming audio data into the queue."""
        if self.recording:
            self.audio_queue.put(indata.copy().flatten())

    def transcription_worker(self):
        """Processes audio chunks in real-time."""
        try:
            if self.model is None:
                GLib.idle_add(self.status_label.set_label, "Loading AI Model (Whisper Tiny)...")
                # Using tiny model for maximum speed to satisfy 'immediate' requirement
                self.model = WhisperModel("tiny", device="cpu", compute_type="int8")
                GLib.idle_add(self.status_label.set_label, "Live Transcription Active")

            audio_buffer = np.array([], dtype=np.float32)

            while self.recording:
                # Gather ~0.75 seconds of audio for a responsive update cycle
                chunks = []
                start_polling = time.time()
                while time.time() - start_polling < 0.75:
                    try:
                        chunk = self.audio_queue.get(timeout=0.1)
                        chunks.append(chunk)
                    except queue.Empty:
                        continue
                
                if not chunks:
                    continue

                # Append to rolling context buffer
                audio_buffer = np.concatenate([audio_buffer] + chunks)

                # Keep only the last 15 seconds to prevent memory bloat and keep inference snappy
                max_samples = 16000 * 15
                if len(audio_buffer) > max_samples:
                    audio_buffer = audio_buffer[-max_samples:]

                # Infer segments
                # beam_size=1 is crucial for "immediate" speed (greedy decoding)
                segments, _ = self.model.transcribe(audio_buffer, beam_size=1, condition_on_previous_text=True)
                
                batch_text = ""
                for segment in segments:
                    batch_text += segment.text + " "
                
                GLib.idle_add(self.update_ui, batch_text.strip())

        except Exception as e:
            print(f"Transcription Failure: {e}")
            GLib.idle_add(self.status_label.set_label, f"Error: {e}")

    def update_ui(self, text):
        if not text:
            return False
            
        buffer = self.text_view.get_buffer()
        buffer.set_text(text)
        
        # Auto-scroll to track live output
        mark = buffer.get_insert()
        self.text_view.scroll_to_mark(mark, 0.0, True, 0.5, 1.0)
        return False

    def on_copy_clicked(self, btn):
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True)
        if text:
            clipboard = self.get_display().get_clipboard()
            clipboard.set(text)
            self.status_label.set_label("Transcript copied!")

if __name__ == "__main__":
    app = DictatorApp()
    app.run(None)
