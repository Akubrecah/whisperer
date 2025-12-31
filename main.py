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
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, GdkPixbuf

# For Global Hotkey and Auto-Paste
from pynput import keyboard

# Robust pathing for installation
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STYLE_FILE = os.path.join(SCRIPT_DIR, "style.css")
SETTINGS_FILE = os.path.expanduser("~/.config/dictator_settings.json")
HISTORY_FILE = os.path.expanduser("~/.config/dictator_history.json")
CLIPBOARD_FILE = os.path.expanduser("~/.config/dictator_clipboards.json")

DEFAULT_SETTINGS = {
    "hotkey": "f8",
    "accent_color": "#39ff14", # Cyber Lime
    "theme": "dark",
    "model": "tiny",
    "auto_paste": True,
    "overlay_image": "/home/akubrecah/Desktop/tech-hub/whisperer/sound-8825_256.gif",
    "monitor_clipboard": True
}

class RecordingOverlay(Gtk.Window):
    def __init__(self, application, image_path):
        super().__init__(application=application)
        self.set_title("Dictator Overlay")
        print(f"DEBUG: Initializing RecordingOverlay with path: {image_path}")
        
        # Internal state for manual GIF playback
        self.anim_iter = None
        self.timeout_id = None
        
        # Make the window strictly non-focusable
        self.set_can_focus(False)
        self.set_focusable(False)
        self.set_can_target(False)
        self.set_decorated(False)
        self.set_resizable(False)
        
        self.set_default_size(400, 600)
        self.add_css_class("overlay-window-transparent")
        
        self.main_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_layout.set_valign(Gtk.Align.END)
        self.main_layout.set_halign(Gtk.Align.CENTER)
        self.main_layout.set_margin_bottom(20)
        self.set_child(self.main_layout)
        
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content_box.add_css_class("recording-overlay-content")
        self.main_layout.append(self.content_box)
        
        self.img = Gtk.Image()
        self.img.set_pixel_size(200)
        self.img.add_css_class("recording-gif-glow")
        self.content_box.append(self.img)
        
        # We'll skip the status label as per user request for "only the gif"
        # self.status_lbl = Gtk.Label(label="CAPTURE ACTIVE")
        # self.status_lbl.add_css_class("overlay-status-text")
        # self.content_box.append(self.status_lbl)
        
        self.load_image(image_path)

    def load_image(self, image_path):
        print(f"DEBUG: Loading overlay asset: {image_path}")
        self.stop_animation()
        
        try:
            if image_path and os.path.exists(image_path):
                anim = GdkPixbuf.PixbufAnimation.new_from_file(image_path)
                if anim.is_static_image():
                    print("DEBUG: Static image detected.")
                    self.img.set_from_file(image_path)
                else:
                    print("DEBUG: Animation detected. Starting manual crank.")
                    self.anim_iter = anim.get_iter()
                    self.start_animation()
            else:
                raise ValueError("Path invalid")
        except Exception as e:
            print(f"DEBUG: Error loading asset: {e}")
            self.img.set_from_icon_name("audio-input-microphone-symbols")

    def start_animation(self):
        if not self.anim_iter: return
        self.update_frame()

    def update_frame(self):
        if not self.anim_iter: return False
        
        pixbuf = self.anim_iter.get_pixbuf()
        self.img.set_from_pixbuf(pixbuf)
        
        self.anim_iter.advance()
        delay = self.anim_iter.get_delay_time()
        if delay < 0: delay = 100
        
        self.timeout_id = GLib.timeout_add(delay, self.update_frame)
        return False

    def stop_animation(self):
        if self.timeout_id:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None
        self.anim_iter = None

    def show_overlay(self):
        self.present()

    def close_overlay(self):
        self.stop_animation()
        self.set_visible(False)

class DictatorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.akubrecah.DictatorV2',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        print("DEBUG: DictatorApp __init__ V2")
        self.settings = self.load_settings()
        self.history = self.load_history()
        self.clipboards = self.load_clipboards()

    def do_startup(self):
        # Startup logic goes here
        Adw.Application.do_startup(self)
        print("DEBUG: Application started (do_startup)")

    def do_activate(self):
        print("DEBUG: Application activating (do_activate)")
        try:
            if not hasattr(self, 'window') or self.window is None:
                print("DEBUG: Instantiating DictatorWindow")
                self.window = DictatorWindow(application=self)
            print("DEBUG: Presenting DictatorWindow")
            self.window.present()
            if self.settings["monitor_clipboard"]:
                self.start_clipboard_monitor()
        except Exception as e:
            print(f"DEBUG: Error in do_activate: {e}")
            import traceback
            traceback.print_exc()

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
            json.dump(self.history[:20], f)

    def add_to_history(self, text):
        if not text or (self.history and self.history[0] == text):
            return
        self.history.insert(0, text)
        self.save_history()

    def load_clipboards(self):
        if os.path.exists(CLIPBOARD_FILE):
            try:
                with open(CLIPBOARD_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return []

    def save_clipboards(self):
        os.makedirs(os.path.dirname(CLIPBOARD_FILE), exist_ok=True)
        with open(CLIPBOARD_FILE, 'w') as f:
            json.dump(self.clipboards[:50], f)

    def add_to_clipboards(self, text):
        if not text or (self.clipboards and self.clipboards[0] == text):
            return
        self.clipboards.insert(0, text)
        self.save_clipboards()
        if hasattr(self, 'window'):
            GLib.idle_add(self.window.refresh_history_ui)

    def start_clipboard_monitor(self):
        threading.Thread(target=self.clipboard_monitor_worker, daemon=True).start()

    def clipboard_monitor_worker(self):
        last_text = ""
        while True:
            try:
                # Use Gdk to get clipboard content from the main thread
                GLib.idle_add(self.check_clipboard)
            except:
                pass
            time.sleep(1.0)

    def check_clipboard(self):
        display = Gdk.Display.get_default()
        if not display: return False
        clipboard = display.get_clipboard()
        clipboard.read_text_async(None, self.on_clipboard_read_finished)
        return False

    def on_clipboard_read_finished(self, clipboard, result):
        text = clipboard.read_text_finish(result)
        if text:
            self.add_to_clipboards(text)

class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, parent):
        super().__init__(transient_for=parent)
        print("DEBUG: PreferencesWindow __init__ V3")
        self.parent = parent
        self.app = parent.get_application()
        page = Adw.PreferencesPage()
        self.add(page)
        
        group = Adw.PreferencesGroup(title="Dictator Core")
        page.add(group)
        
        # Hotkey setting
        hotkey_row = Adw.EntryRow(title="Global Hotkey", text=self.app.settings["hotkey"])
        hotkey_row.connect("changed", self.on_hotkey_changed)
        group.add(hotkey_row)
        
        # Color Picker Row
        color_row = Adw.ActionRow(title="Accent Color Glow")
        self.color_btn = Gtk.ColorButton()
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

        # New: Overlay Image Selection
        overlay_row = Adw.ActionRow(title="Recording Overlay (GIF/Image)")
        overlay_btn = Gtk.Button(label="Select File")
        overlay_btn.connect("clicked", self.on_overlay_pick_clicked)
        overlay_row.add_suffix(overlay_btn)
        group.add(overlay_row)

        # New: Clipboard Monitoring Toggle
        cb_row = Adw.SwitchRow(title="Monitor System Clipboard", active=self.app.settings["monitor_clipboard"])
        cb_row.connect("notify::active", self.on_clipboard_toggle)
        group.add(cb_row)

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

    def on_clipboard_toggle(self, row, pspec):
        self.app.settings["monitor_clipboard"] = row.get_active()
        self.app.save_settings()

    def on_overlay_pick_clicked(self, btn):
        print("DEBUG: Overlay pick clicked")
        dialog = Gtk.FileDialog(title="Select Recording Overlay (GIF/Image)")
        
        # Add file filters
        filters = Gio.ListStore.new(Gtk.FileFilter)
        
        f_images = Gtk.FileFilter()
        f_images.set_name("Image files")
        f_images.add_mime_type("image/gif")
        f_images.add_mime_type("image/png")
        f_images.add_mime_type("image/jpeg")
        filters.append(f_images)
        
        dialog.set_filters(filters)
        dialog.open(self, None, self.on_overlay_file_selected)

    def on_overlay_file_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                print(f"DEBUG: File selected: {path}")
                self.app.settings["overlay_image"] = path
                self.app.save_settings()
                
                # IMPORTANT: Update the live overlay if it exists
                if hasattr(self.parent, 'overlay') and self.parent.overlay:
                    print("DEBUG: Updating active overlay instance image")
                    self.parent.overlay.load_image(path)
            else:
                print("DEBUG: Selection cancelled")
        except Exception as e:
            print(f"DEBUG: File selection error: {e}")

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
        self.overlay = None
        
        self.setup_ui()
        self.apply_css()
        self.update_hotkey()

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        try:
            if not os.path.exists(STYLE_FILE):
                return
            with open(STYLE_FILE, "r") as f:
                css_data = f.read()
            css_data = css_data.replace("--neon-accent: #39ff14;", f"--neon-accent: {self.app.settings['accent_color']};")
            css_provider.load_from_data(css_data, len(css_data))
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except: pass

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
        
        popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        popover_box.set_margin_top(10)
        popover_box.set_margin_bottom(10)
        popover_box.set_margin_start(10)
        popover_box.set_margin_end(10)
        self.history_popover.set_child(popover_box)
        
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(stack)
        popover_box.append(switcher)
        popover_box.append(stack)
        
        self.history_list = Gtk.ListBox()
        self.history_list.set_selection_mode(Gtk.SelectionMode.NONE)
        history_scroll = Gtk.ScrolledWindow(min_content_height=400, min_content_width=350)
        history_scroll.set_child(self.history_list)
        stack.add_titled(history_scroll, "transmissions", "🎙️ Transcripts")
        
        self.clipboard_list = Gtk.ListBox()
        self.clipboard_list.set_selection_mode(Gtk.SelectionMode.NONE)
        clipboard_scroll = Gtk.ScrolledWindow(min_content_height=400, min_content_width=350)
        clipboard_scroll.set_child(self.clipboard_list)
        stack.add_titled(clipboard_scroll, "clipboards", "📋 Clipboard History")

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

    def refresh_history_ui(self):
        # Refresh transcripts
        while (child := self.history_list.get_first_child()): self.history_list.remove(child)
        if not self.app.history: self.history_list.append(Gtk.Label(label="No recent transmissions"))
        else:
            for item in self.app.history:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                label = Gtk.Label(label=item[:40] + ("..." if len(item) > 40 else ""))
                label.set_hexpand(True)
                label.set_halign(Gtk.Align.START)
                copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
                copy_btn.connect("clicked", lambda b, t=item: self.copy_text_to_clipboard(t))
                row.append(label); row.append(copy_btn); self.history_list.append(row)

        # Refresh clipboards
        while (child := self.clipboard_list.get_first_child()): self.clipboard_list.remove(child)
        if not self.app.clipboards: self.clipboard_list.append(Gtk.Label(label="Clipboard history is empty"))
        else:
            for item in self.app.clipboards:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                label = Gtk.Label(label=item[:40] + ("..." if len(item) > 40 else ""))
                label.set_hexpand(True); label.set_halign(Gtk.Align.START)
                copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
                copy_btn.connect("clicked", lambda b, t=item: self.copy_text_to_clipboard(t))
                row.append(label); row.append(copy_btn); self.clipboard_list.append(row)

    def on_history_clicked(self, btn):
        self.refresh_history_ui()
        self.history_popover.popup()

    def copy_text_to_clipboard(self, text):
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)
        self.status_label.set_label("Copied to clipboard! 📋")
        self.history_popover.popdown()

    def on_preferences_clicked(self, btn):
        prefs = PreferencesWindow(self)
        prefs.present()

    def update_hotkey(self):
        if hasattr(self, 'listener'): self.listener.stop()
        key_name = self.app.settings["hotkey"]
        try:
            if hasattr(keyboard.Key, key_name): self.trigger_key = getattr(keyboard.Key, key_name)
            else: self.trigger_key = keyboard.KeyCode.from_char(key_name)
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
        if not self.recording: self.start_live_session()
        else: self.stop_live_session(False)

    def start_live_session(self):
        if self.recording: return
        self.recording = True
        print("DEBUG: Starting live session...")
        self.orb_btn.add_css_class("recording")
        self.orb_label.set_label("LISTENING")
        
        # Show Overlay
        if self.overlay is None:
            print(f"DEBUG: Creating new RecordingOverlay instance. App settings path: {self.app.settings['overlay_image']}")
            self.overlay = RecordingOverlay(self.app, self.app.settings["overlay_image"])
        self.overlay.show_overlay()
        
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
        print("DEBUG: Stopping live session...")
        self.orb_btn.remove_css_class("recording")
        self.orb_label.set_label("READY")
        
        # Hide Overlay
        if self.overlay:
            print("DEBUG: Hiding overlay")
            self.overlay.close_overlay()
            # We don't destroy it to keep it fast for next time, but we might want to update image
            # if settings changed. For now just hide.
        
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        
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
        except: pass

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
        try:
            clipboard = self.get_display().get_clipboard()
            clipboard.set(self.current_transcript)
            time.sleep(0.1)
            with self.keyboard_controller.pressed(keyboard.Key.ctrl):
                self.keyboard_controller.press('v')
                self.keyboard_controller.release('v')
            self.status_label.set_label("DATA TRANSMITTED ⚡")
        except: pass
        return False

if __name__ == "__main__":
    try:
        print("DEBUG: Application starting...")
        adw_app = DictatorApp()
        status = adw_app.run(None)
        print(f"DEBUG: Application exited with status: {status}")
    except Exception as e:
        print(f"DEBUG: Critical error during execution: {e}")
        import traceback
        traceback.print_exc()
