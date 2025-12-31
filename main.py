import os
import threading
import queue
import time
import json
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

# Robust pathing for installation
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STYLE_FILE = os.path.join(SCRIPT_DIR, "style.css")
SETTINGS_FILE = os.path.expanduser("~/.config/dictator_settings.json")
HISTORY_FILE = os.path.expanduser("~/.config/dictator_history.json")

DEFAULT_SETTINGS = {
    "hotkey": "f8",
    "accent_color": "#39ff14", # Cyber Lime
    "theme": "dark",
    "model": "tiny",
    "auto_paste": True
}

class DictatorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.Dictator',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.settings = self.load_settings()
        self.history = self.load_history()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    return {**DEFAULT_SETTINGS, **json.load(f)}
            except:
                pass
        return DEFAULT_SETTINGS.copy()

    def save_settings(self):
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(self.settings, f)

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return []

    def save_history(self):
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history[:20], f) # Keep last 20

    def add_to_history(self, text):
        if not text or (self.history and self.history[0] == text):
            return
        self.history.insert(0, text)
        self.save_history()

    def do_activate(self):
        self.window = DictatorWindow(application=self)
        self.window.present()

class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, parent):
        super().__init__(transient_for=parent)
        self.parent = parent
        self.app = parent.get_application()
        
        page = Adw.PreferencesPage()
        self.add(page)
        
        group = Adw.PreferencesGroup(title="User Desires")
        page.add(group)
        
        # Hotkey setting
        hotkey_row = Adw.EntryRow(title="Global Hotkey", text=self.app.settings["hotkey"])
        hotkey_row.connect("changed", self.on_hotkey_changed)
        group.add(hotkey_row)
        
        # Color Picker Row
        color_row = Adw.ActionRow(title="Accent Color Glow")
        self.color_btn = Gtk.ColorButton()
        # Set initial color
        rgba = Gdk.RGBA()
        rgba.parse(self.app.settings["accent_color"])
        self.color_btn.set_rgba(rgba)
        self.color_btn.connect("color-set", self.on_color_set)
        color_row.add_suffix(self.color_btn)
        group.add(color_row)

        # Model selection
        model_row = Adw.ComboRow(title="AI Model", selected=0 if self.app.settings["model"] == "tiny" else 1)
        model_row.set_model(Gtk.StringList.new(["Tiny (Fastest)", "Base (Balanced)"]))
        model_row.connect("notify::selected", self.on_model_changed)
        group.add(model_row)

    def on_hotkey_changed(self, row):
        new_key = row.get_text().lower()
        if new_key:
            self.app.settings["hotkey"] = new_key
            self.app.save_settings()
            self.parent.update_hotkey()

    def on_color_set(self, btn):
        rgba = btn.get_rgba()
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
        )
        self.app.settings["accent_color"] = hex_color
        self.app.save_settings()
        self.parent.apply_css()

    def on_model_changed(self, row, pspec):
        models = ["tiny", "base"]
        self.app.settings["model"] = models[row.get_selected()]
        self.app.save_settings()
        self.parent.model = None

class DictatorWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = kwargs["application"]
        
        self.set_title("Dictator")
        self.set_default_size(800, 600)
        self.add_css_class("futuristic-window")

        # State
        self.recording = False
        self.audio_queue = queue.Queue()
        self.model = None
        self.current_transcript = ""
        self.keyboard_controller = keyboard.Controller()
        
        self.setup_ui()
        self.apply_css()
        self.update_hotkey()

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        try:
            if not os.path.exists(STYLE_FILE):
                print(f"CSS not found at {STYLE_FILE}")
                return
            with open(STYLE_FILE, "r") as f:
                css_data = f.read()
            
            css_data = css_data.replace("--neon-accent: #39ff14;", f"--neon-accent: {self.app.settings['accent_color']};")
            
            css_provider.load_from_data(css_data, len(css_data))
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(f"CSS Error: {e}")

    def setup_ui(self):
        view_stack = Adw.ToolbarView()
        self.set_content(view_stack)

        header = Adw.HeaderBar()
        view_stack.add_top_bar(header)
        
        # History Button
        history_btn = Gtk.Button(icon_name="document-open-recent-symbolic")
        history_btn.connect("clicked", self.on_history_clicked)
        header.pack_start(history_btn)
        
        # History Popover
        self.history_popover = Gtk.Popover()
        self.history_popover.set_parent(history_btn)
        self.history_list = Gtk.ListBox()
        self.history_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.history_list.set_margin_top(10)
        self.history_list.set_margin_bottom(10)
        self.history_list.set_margin_start(10)
        self.history_list.set_margin_end(10)
        
        scrolled_history = Gtk.ScrolledWindow()
        scrolled_history.set_min_content_height(300)
        scrolled_history.set_min_content_width(300)
        scrolled_history.set_child(self.history_list)
        self.history_popover.set_child(scrolled_history)

        # Settings Button
        settings_btn = Gtk.Button(icon_name="emblem-system-symbolic")
        settings_btn.connect("clicked", self.on_preferences_clicked)
        header.pack_end(settings_btn)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(30)
        main_box.set_margin_bottom(30)
        main_box.set_margin_start(30)
        main_box.set_margin_end(30)
        view_stack.set_content(main_box)

        # Visual Orb
        self.orb_btn = Gtk.Button()
        self.orb_btn.add_css_class("record-orb")
        self.orb_btn.set_halign(Gtk.Align.CENTER)
        self.orb_btn.connect("clicked", self.on_record_toggled)
        
        overlay = Gtk.Overlay()
        overlay.set_child(self.orb_btn)
        self.orb_label = Gtk.Label(label="READY")
        self.orb_label.add_css_class("status-caption")
        overlay.add_overlay(self.orb_label)
        main_box.append(overlay)

        # Text area
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.add_css_class("glass-view")
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolled.set_child(self.text_view)
        main_box.append(scrolled)

        self.status_label = Gtk.Label(label="Initializing neural systems...")
        self.status_label.add_css_class("caption")
        main_box.append(self.status_label)

    def on_history_clicked(self, btn):
        # Refresh history list
        while (child := self.history_list.get_first_child()):
            self.history_list.remove(child)
        
        if not self.app.history:
            self.history_list.append(Gtk.Label(label="No recent transmissions"))
        else:
            for item in self.app.history:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                label = Gtk.Label(label=item[:40] + ("..." if len(item) > 40 else ""))
                label.set_hexpand(True)
                label.set_halign(Gtk.Align.START)
                
                copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
                copy_btn.connect("clicked", lambda b, t=item: self.copy_text_to_clipboard(t))
                
                row.append(label)
                row.append(copy_btn)
                self.history_list.append(row)
        
        self.history_popover.popup()

    def copy_text_to_clipboard(self, text):
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)
        self.status_label.set_label("History item copied! 📋")
        self.history_popover.popdown()

    def on_preferences_clicked(self, btn):
        prefs = PreferencesWindow(self)
        prefs.present()

    def update_hotkey(self):
        if hasattr(self, 'listener'):
            self.listener.stop()
        key_name = self.app.settings["hotkey"]
        try:
            if hasattr(keyboard.Key, key_name):
                self.trigger_key = getattr(keyboard.Key, key_name)
            else:
                self.trigger_key = keyboard.KeyCode.from_char(key_name)
            self.listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
            self.listener.start()
        except: pass

    def on_key_press(self, key):
        if key == self.trigger_key and not self.recording:
            GLib.idle_add(self.start_live_session)

    def on_key_release(self, key):
        if key == self.trigger_key and self.recording:
            GLib.idle_add(self.stop_live_session, True)

    def on_record_toggled(self, btn):
        if not self.recording:
            self.start_live_session()
        else:
            self.stop_live_session(False)

    def start_live_session(self):
        if self.recording: return
        self.recording = True
        self.orb_btn.add_css_class("recording")
        self.orb_label.set_label("LISTENING")
        self.status_label.set_label("Capture in progress...")
        self.current_transcript = ""
        self.text_view.get_buffer().set_text("")
        while not self.audio_queue.empty(): self.audio_queue.get()
        self.stream = sd.InputStream(samplerate=16000, channels=1, callback=self.audio_callback)
        self.stream.start()
        threading.Thread(target=self.transcription_worker, daemon=True).start()

    def stop_live_session(self, auto_paste=False):
        if not self.recording: return
        self.recording = False
        self.orb_btn.remove_css_class("recording")
        self.orb_label.set_label("READY")
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        
        # Add to history
        if self.current_transcript:
            self.app.add_to_history(self.current_transcript)

        if auto_paste:
            threading.Thread(target=self.wait_and_paste, daemon=True).start()
        else:
            self.status_label.set_label("Session finished.")

    def audio_callback(self, indata, frames, time, status):
        if self.recording: self.audio_queue.put(indata.copy().flatten())

    def transcription_worker(self):
        try:
            if self.model is None:
                self.model = WhisperModel(self.app.settings["model"], device="cpu", compute_type="int8")
            audio_buffer = np.array([], dtype=np.float32)
            while self.recording:
                chunks = []
                start = time.time()
                while time.time() - start < 0.6:
                    try: chunks.append(self.audio_queue.get(timeout=0.1))
                    except queue.Empty: continue
                if not chunks: continue
                audio_buffer = np.concatenate([audio_buffer] + chunks)
                if len(audio_buffer) > 16000 * 15: audio_buffer = audio_buffer[-(16000 * 15):]
                segments, _ = self.model.transcribe(audio_buffer, beam_size=1)
                text = " ".join([s.text for s in segments]).strip()
                self.current_transcript = text
                GLib.idle_add(self.update_ui, text)
        except Exception as e: print(f"Error: {e}")

    def update_ui(self, text):
        if text:
            self.text_view.get_buffer().set_text(text)
            mark = self.text_view.get_buffer().get_insert()
            self.text_view.scroll_to_mark(mark, 0.0, True, 0.5, 1.0)
        return False

    def wait_and_paste(self):
        time.sleep(0.4)
        GLib.idle_add(self.perform_auto_paste)

    def perform_auto_paste(self):
        if not self.current_transcript: return False
        clipboard = self.get_display().get_clipboard()
        clipboard.set(self.current_transcript)
        time.sleep(0.1)
        with self.keyboard_controller.pressed(keyboard.Key.ctrl):
            self.keyboard_controller.press('v')
            self.keyboard_controller.release('v')
        self.status_label.set_label("DATA TRANSMITTED ⚡")
        return False

if __name__ == "__main__":
    adw_app = DictatorApp()
    adw_app.run(None)
