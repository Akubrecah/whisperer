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

# For Global Hotkey and Auto-Paste
from pynput import keyboard

class DictatorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.Dictator',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        self.window = DictatorWindow(application=self)
        self.window.present()

class DictatorWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("Dictator - Hold F8 to Talk")
        self.set_default_size(700, 500)

        # State management
        self.recording = False
        self.audio_queue = queue.Queue()
        self.model = None
        self.current_transcript = ""
        
        # Keyboard Controller for Auto-Paste
        self.keyboard_controller = keyboard.Controller()
        self.trigger_key = keyboard.Key.f8 # Default Hotkey
        
        # UI Setup
        self.setup_ui()
        
        # Start Global Listener
        self.start_hotkey_listener()

    def setup_ui(self):
        view_stack = Adw.ToolbarView()
        self.set_content(view_stack)

        header = Adw.HeaderBar()
        view_stack.add_top_bar(header)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        view_stack.set_content(main_box)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(300)
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolled.set_child(self.text_view)
        main_box.append(scrolled)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        main_box.append(button_box)

        self.record_btn = Gtk.Button(label="Start (or hold F8)")
        self.record_btn.add_css_class("suggested-action")
        self.record_btn.add_css_class("pill")
        self.record_btn.connect("clicked", self.on_record_toggled)
        button_box.append(self.record_btn)

        self.copy_btn = Gtk.Button(label="Copy Transcript")
        self.copy_btn.connect("clicked", self.on_copy_clicked)
        button_box.append(self.copy_btn)

        self.status_label = Gtk.Label(label=f"Hold {self.trigger_key} to dictate globally")
        self.status_label.add_css_class("caption")
        main_box.append(self.status_label)

    def start_hotkey_listener(self):
        """Initializes the background listener for global key events."""
        self.listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.listener.start()

    def on_key_press(self, key):
        if key == self.trigger_key and not self.recording:
            GLib.idle_add(self.start_live_session)

    def on_key_release(self, key):
        if key == self.trigger_key and self.recording:
            GLib.idle_add(self.stop_live_session, True) # True means auto-paste

    def on_record_toggled(self, btn):
        if not self.recording:
            self.start_live_session()
        else:
            self.stop_live_session(False)

    def start_live_session(self):
        if self.recording: return
        self.recording = True
        self.record_btn.set_label("Listening...")
        self.record_btn.remove_css_class("suggested-action")
        self.record_btn.add_css_class("destructive-action")
        self.status_label.set_label("Recording... Speak now!")

        self.current_transcript = ""
        self.text_view.get_buffer().set_text("")
        while not self.audio_queue.empty():
            self.audio_queue.get()

        self.stream = sd.InputStream(samplerate=16000, channels=1, callback=self.audio_callback)
        self.stream.start()
        threading.Thread(target=self.transcription_worker, daemon=True).start()

    def stop_live_session(self, auto_paste=False):
        if not self.recording: return
        self.recording = False
        self.record_btn.set_label("Start (or hold F8)")
        self.record_btn.remove_css_class("destructive-action")
        self.record_btn.add_css_class("suggested-action")
        self.status_label.set_label("Processing final segments...")
        
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()

        if auto_paste:
            # Short delay to ensure final transcription chunk is processed
            threading.Thread(target=self.wait_and_paste, daemon=True).start()
        else:
            self.status_label.set_label("Done.")

    def audio_callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_queue.put(indata.copy().flatten())

    def transcription_worker(self):
        try:
            if self.model is None:
                GLib.idle_add(self.status_label.set_label, "Loading AI model...")
                self.model = WhisperModel("tiny", device="cpu", compute_type="int8")
                GLib.idle_add(self.status_label.set_label, "Ready!")

            audio_buffer = np.array([], dtype=np.float32)

            while self.recording:
                chunks = []
                start_poll = time.time()
                while time.time() - start_poll < 0.6: # Faster cycle for immediacy
                    try:
                        chunk = self.audio_queue.get(timeout=0.1)
                        chunks.append(chunk)
                    except queue.Empty:
                        continue
                
                if not chunks: continue
                audio_buffer = np.concatenate([audio_buffer] + chunks)
                
                # Context window for live updates
                if len(audio_buffer) > 16000 * 10:
                    audio_buffer = audio_buffer[-(16000 * 10):]

                segments, _ = self.model.transcribe(audio_buffer, beam_size=1)
                text = " ".join([s.text for s in segments]).strip()
                self.current_transcript = text
                GLib.idle_add(self.update_ui, text)

        except Exception as e:
            print(f"Inference error: {e}")

    def update_ui(self, text):
        if text:
            self.text_view.get_buffer().set_text(text)
            mark = self.text_view.get_buffer().get_insert()
            self.text_view.scroll_to_mark(mark, 0.0, True, 0.5, 1.0)
        return False

    def wait_and_paste(self):
        """Wait for the worker to finish the last chunk, then paste."""
        time.sleep(0.3)
        GLib.idle_add(self.perform_auto_paste)

    def perform_auto_paste(self):
        text = self.current_transcript
        if not text:
            self.status_label.set_label("No text captured to paste.")
            return False

        # 1. Copy to clipboard
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)
        
        # 2. Simulate Paste
        # Give the system a fraction of a second to sync clipboard
        time.sleep(0.1)
        with self.keyboard_controller.pressed(keyboard.Key.ctrl):
            self.keyboard_controller.press('v')
            self.keyboard_controller.release('v')
        
        self.status_label.set_label("Transcribed and Pasted! ⚡")
        return False

    def on_copy_clicked(self, btn):
        if self.current_transcript:
            clipboard = self.get_display().get_clipboard()
            clipboard.set(self.current_transcript)
            self.status_label.set_label("Transcript copied!")

if __name__ == "__main__":
    app = DictatorApp()
    app.run(None)
