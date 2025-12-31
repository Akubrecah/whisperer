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
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, GdkPixbuf, GObject

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
    "accent_color": "#ff7c00", # Shlumzi Amber
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
        self.set_keep_above(True)
        
        # Get monitor geometry for placement
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        # Get monitor geometry to span the whole screen
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        if monitors.get_n_items() > 0:
            monitor = monitors.get_item(0)
            geometry = monitor.get_geometry()
            self.set_default_size(geometry.width, geometry.height)
        else:
            self.set_default_size(1920, 1080)

        self.add_css_class("overlay-window-transparent")
        
        # Main layout spans the whole screen
        self.main_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_layout.add_css_class("overlay-window-transparent")
        self.main_layout.set_hexpand(True)
        self.main_layout.set_vexpand(True)
        self.set_child(self.main_layout)
        
        # Content box pushed to bottom-center
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content_box.add_css_class("recording-overlay-content")
        self.content_box.set_valign(Gtk.Align.END)
        self.content_box.set_halign(Gtk.Align.CENTER)
        self.content_box.set_margin_bottom(50) # Buffer from taskbar
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
        Adw.Application.do_startup(self)
        print("DEBUG: Application started (do_startup)")
        # Prune history every 5 minutes
        GLib.timeout_add_seconds(300, self.prune_history)

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
                    data = json.load(f)
                    # Migration: convert string list to object list
                    if data and isinstance(data[0], str):
                        return [{"text": t, "timestamp": time.time(), "pinned": False} for t in data]
                    return data
            except:
                pass
        return []

    def save_history(self):
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history, f)

    def add_to_history(self, text):
        if not text or (self.history and self.history[0]["text"] == text):
            return
        self.history.insert(0, {"text": text, "timestamp": time.time(), "pinned": False})
        self.save_history()
        
        # Trigger UI refresh if active
        if hasattr(self, 'window') and self.window:
            GLib.idle_add(self.window.refresh_history_ui)

    def load_clipboards(self):
        if os.path.exists(CLIPBOARD_FILE):
            try:
                with open(CLIPBOARD_FILE, 'r') as f:
                    data = json.load(f)
                    # Migration: convert string list to object list
                    if data and isinstance(data[0], str):
                        return [{"text": t, "timestamp": time.time(), "pinned": False} for t in data]
                    return data
            except:
                pass
        return []

    def save_clipboards(self):
        os.makedirs(os.path.dirname(CLIPBOARD_FILE), exist_ok=True)
        with open(CLIPBOARD_FILE, 'w') as f:
            json.dump(self.clipboards, f)

    def add_to_clipboards(self, text):
        if not text or (self.clipboards and self.clipboards[0]["text"] == text):
            return
        self.clipboards.insert(0, {"text": text, "timestamp": time.time(), "pinned": False})
        self.save_clipboards()
        if hasattr(self, 'window') and self.window:
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

    def reorder_history(self, from_idx, to_idx):
        if from_idx == to_idx: return
        item = self.history.pop(from_idx)
        self.history.insert(to_idx, item)
        self.save_history()
        GLib.idle_add(self.window.refresh_history_ui)

    def reorder_clipboards(self, from_idx, to_idx):
        if from_idx == to_idx: return
        item = self.clipboards.pop(from_idx)
        self.clipboards.insert(to_idx, item)
        self.save_clipboards()
        GLib.idle_add(self.window.refresh_history_ui)

    def prune_history(self):
        now = time.time()
        expiry = 3600 # 1 hour
        changed = False
        
        # Prune Transcripts
        new_history = [item for item in self.history if item.get("pinned") or (now - item["timestamp"] < expiry)]
        if len(new_history) != len(self.history):
            self.history = new_history
            self.save_history()
            changed = True
            
        # Prune Clipboards
        new_clipboards = [item for item in self.clipboards if item.get("pinned") or (now - item["timestamp"] < expiry)]
        if len(new_clipboards) != len(self.clipboards):
            self.clipboards = new_clipboards
            self.save_clipboards()
            changed = True
            
        if changed and hasattr(self, 'window') and self.window:
            GLib.idle_add(self.window.refresh_history_ui)
            
        return True # Keep timeout running

    def check_clipboard(self):
        display = Gdk.Display.get_default()
        if not display: return False
        clipboard = display.get_clipboard()
        clipboard.read_text_async(None, self.on_clipboard_read_finished)
        return False

    def on_clipboard_read_finished(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
            if text:
                self.add_to_clipboards(text)
        except GLib.Error:
            # Silence error when clipboard doesn't contain plain text (e.g. image, file)
            pass
        except Exception as e:
            print(f"DEBUG: Unexpected clipboard error: {e}")


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
        self.refresh_history_ui()
        self.apply_css()
        self.update_hotkey()

    # Settings Handlers
    def on_hotkey_changed(self, row):
        new_key = row.get_text().lower()
        if new_key:
            self.app.settings["hotkey"] = new_key
            self.app.save_settings()
            self.update_hotkey()

    def on_color_set(self, btn):
        rgba = btn.rgba
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
        )
        self.app.settings["accent_color"] = hex_color
        self.app.save_settings()
        self.apply_css()

    def on_model_changed(self, row, pspec):
        models = ["tiny", "base"]
        self.app.settings["model"] = models[row.get_selected()]
        self.app.save_settings()
        self.model = None

    def on_clipboard_toggle(self, row, pspec):
        self.app.settings["monitor_clipboard"] = row.get_active()
        self.app.save_settings()
        if self.app.settings["monitor_clipboard"]:
            self.app.start_clipboard_monitor()

    def on_paste_toggled(self, row, pspec):
        self.app.settings["auto_paste"] = row.get_active()
        self.app.save_settings()

    def on_overlay_pick_clicked(self, btn):
        dialog = Gtk.FileDialog(title="Select Recording Overlay (GIF/Image)")
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
                self.app.settings["overlay_image"] = path
                self.app.save_settings()
                if self.overlay:
                    self.overlay.close_overlay() # This is a custom method in RecordingOverlay
                    self.overlay = None
            else:
                print("DEBUG: Selection cancelled")
        except Exception as e:
            print(f"DEBUG: Error selecting overlay: {e}")

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        try:
            if not os.path.exists(STYLE_FILE):
                return
            with open(STYLE_FILE, "r") as f:
                css_data = f.read()
            css_data = css_data.replace("--neon-accent: #ff7c00;", f"--neon-accent: {self.app.settings['accent_color']};")
            css_provider.load_from_data(css_data, len(css_data))
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except: pass

    def setup_ui(self):
        # Use a main box to hold the header and the content
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header with navigation
        header = Adw.HeaderBar()
        main_box.append(header)
        
        self.view_stack = Adw.ViewStack()
        self.view_stack.set_vexpand(True)
        main_box.append(self.view_stack)

        view_switcher = Adw.ViewSwitcher()
        view_switcher.set_stack(self.view_stack)
        header.set_title_widget(view_switcher)

        # 1. DASHBOARD PAGE
        self.dashboard_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        self.dashboard_box.set_margin_top(30)
        self.dashboard_box.set_margin_bottom(30)
        self.dashboard_box.set_margin_start(30)
        self.dashboard_box.set_margin_end(30)
        
        dashboard_page = self.view_stack.add_titled_with_icon(self.dashboard_box, "dashboard", "Dashboard", "app-dashboard-symbolic")
        
        # Left Column: Orb and Text
        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        left_col.set_hexpand(True)
        self.dashboard_box.append(left_col)

        # Right Column: Dashboard Clipboards
        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right_col.set_size_request(280, -1)
        right_col.add_css_class("glass-view")
        right_col.set_margin_start(10)
        
        clip_label = Gtk.Label(label="📋 RECENT CLIPBOARDS")
        clip_label.add_css_class("caption")
        clip_label.set_margin_top(10)
        right_col.append(clip_label)

        self.dashboard_clipboard_list = Gtk.ListBox()
        self.dashboard_clipboard_list.set_selection_mode(Gtk.SelectionMode.NONE)
        dash_clip_scroll = Gtk.ScrolledWindow()
        dash_clip_scroll.set_vexpand(True)
        dash_clip_scroll.set_child(self.dashboard_clipboard_list)
        right_col.append(dash_clip_scroll)
        self.dashboard_box.append(right_col)

        # Populate Left Column (Orb and Text area)
        self.orb_btn = Gtk.Button()
        self.orb_btn.add_css_class("record-orb")
        self.orb_btn.set_halign(Gtk.Align.CENTER)
        self.orb_btn.connect("clicked", self.on_record_toggled)
        
        orbital_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        orbital_box.add_css_class("orbital-container")
        orbital_box.set_halign(Gtk.Align.CENTER)
        orbital_box.set_valign(Gtk.Align.CENTER)
        left_col.append(orbital_box)

        overlay = Gtk.Overlay()
        overlay.set_child(self.orb_btn)
        self.orb_label = Gtk.Label(label="READY")
        self.orb_label.add_css_class("status-caption")
        overlay.add_overlay(self.orb_label)
        orbital_box.append(overlay)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.add_css_class("glass-view")
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolled.set_child(self.text_view)
        left_col.append(scrolled)

        self.status_label = Gtk.Label(label="Initializing neural systems...")
        self.status_label.add_css_class("caption")
        left_col.append(self.status_label)

        # 2. SETTINGS PAGE
        settings_page = Adw.PreferencesPage()
        self.view_stack.add_titled_with_icon(settings_page, "settings", "Settings", "emblem-system-symbolic")
        
        core_group = Adw.PreferencesGroup(title="Dictator Core")
        settings_page.add(core_group)
        
        # Hotkey setting
        hotkey_row = Adw.EntryRow(title="Global Hotkey", text=self.app.settings["hotkey"])
        hotkey_row.connect("changed", self.on_hotkey_changed)
        core_group.add(hotkey_row)
        
        # Color Picker Row
        color_row = Adw.ActionRow(title="Accent Color Glow")
        self.color_btn = Gtk.ColorButton()
        rgba = Gdk.RGBA()
        rgba.parse(self.app.settings["accent_color"])
        self.color_btn.rgba = rgba
        self.color_btn.connect("color-set", self.on_color_set)
        color_row.add_suffix(self.color_btn)
        core_group.add(color_row)

        # Model selection
        model_row = Adw.ComboRow(title="AI Model", selected=0 if self.app.settings["model"] == "tiny" else 1)
        model_row.set_model(Gtk.StringList.new(["Tiny (Fastest)", "Base (Balanced)"]))
        model_row.connect("notify::selected", self.on_model_changed)
        core_group.add(model_row)

        # Overlay Image Selection
        overlay_row = Adw.ActionRow(title="Recording Overlay (GIF/Image)")
        overlay_btn = Gtk.Button(label="Select File")
        overlay_btn.connect("clicked", self.on_overlay_pick_clicked)
        overlay_row.add_suffix(overlay_btn)
        core_group.add(overlay_row)
        
        # Auto Paste Toggle
        paste_row = Adw.SwitchRow(title="Auto-Paste on Release", active=self.app.settings["auto_paste"])
        paste_row.connect("notify::active", self.on_paste_toggled)
        core_group.add(paste_row)
        
        # Clipboard Monitor Toggle
        clip_row = Adw.SwitchRow(title="Monitor Clipboard History", active=self.app.settings["monitor_clipboard"])
        clip_row.connect("notify::active", self.on_clipboard_toggle)
        core_group.add(clip_row)

        # Rest of headers/buttons
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
        
        self.history_list = Gtk.ListBox()
        self.history_list.set_selection_mode(Gtk.SelectionMode.NONE)
        history_scroll = Gtk.ScrolledWindow(min_content_height=400, min_content_width=350)
        history_scroll.set_child(self.history_list)
        popover_box.append(history_scroll)
        
        # We'll use the switcher in dashboard or somewhere else if needed, but for now 
        # let's keep the popover simple for transcripts.


    def refresh_history_ui(self):
        # Refresh transcripts
        while (child := self.history_list.get_first_child()): self.history_list.remove(child)
        if not self.app.history: self.history_list.append(Gtk.Label(label="No recent transmissions"))
        else:
            for i, item in enumerate(self.app.history):
                text = item["text"]
                pinned = item.get("pinned", False)
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                row.add_css_class("history-row")
                
                # Add drag handle/icon
                drag_handle = Gtk.Image(icon_name="view-more-symbolic")
                drag_handle.set_opacity(0.5)
                row.append(drag_handle)
                
                label = Gtk.Label(label=text[:40] + ("..." if len(text) > 40 else ""))
                label.set_hexpand(True)
                label.set_halign(Gtk.Align.START)
                
                pin_btn = Gtk.Button(icon_name="pinnable-symbolic" if not pinned else "pin-symbolic")
                pin_btn.add_css_class("flat")
                pin_btn.connect("clicked", self.on_toggle_pin, "history", i)
                
                copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
                copy_btn.connect("clicked", lambda b, t=text: self.copy_text_to_clipboard(t))
                
                row.append(pin_btn); row.append(label); row.append(copy_btn)
                
                # Drag & Drop Support
                source = Gtk.DragSource.new()
                source.set_actions(Gdk.DragAction.MOVE)
                source.connect("prepare", self.on_drag_prepare, "history", i)
                row.add_controller(source)
                
                target = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
                target.connect("drop", self.on_drop_row, "history", i)
                row.add_controller(target)
                
                self.history_list.append(row)

        # Refresh clipboards
        for lb in [self.dashboard_clipboard_list]:
            while (child := lb.get_first_child()): lb.remove(child)
            if not self.app.clipboards:
                lb.append(Gtk.Label(label="Clipboard history is empty"))
            else:
                for i, item in enumerate(self.app.clipboards):
                    text = item["text"]
                    pinned = item.get("pinned", False)
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                    row.add_css_class("clipboard-row")
                    
                    label = Gtk.Label(label=text[:40] + ("..." if len(text) > 40 else ""))
                    label.set_hexpand(True); label.set_halign(Gtk.Align.START)
                    
                    pin_btn = Gtk.Button(icon_name="pinnable-symbolic" if not pinned else "pin-symbolic")
                    pin_btn.add_css_class("flat")
                    pin_btn.connect("clicked", self.on_toggle_pin, "clipboard", i)
                    
                    copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
                    copy_btn.connect("clicked", lambda b, t=text: self.copy_text_to_clipboard(t))
                    
                    row.append(pin_btn); row.append(label); row.append(copy_btn)
                    
                    # Drag & Drop Support
                    source = Gtk.DragSource.new()
                    source.set_actions(Gdk.DragAction.MOVE)
                    source.connect("prepare", self.on_drag_prepare, "clipboard", i)
                    row.add_controller(source)
                    
                    dt = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
                    dt.connect("drop", self.on_drop_row, "clipboard", i)
                    row.add_controller(dt)
                    
                    lb.append(row)

    def on_drag_prepare(self, source, x, y, type, index):
        # We wrap the index in a Gdk.ContentProvider
        # In modern GTK4 we use GValue
        value = GObject.Value()
        value.init(GObject.TYPE_INT)
        value.set_int(index)
        return Gdk.ContentProvider.new_for_value(value)

    def on_drop_row(self, target, value, x, y, type, to_idx):
        from_idx = value
        if type == "history": self.app.reorder_history(from_idx, to_idx)
        else: self.app.reorder_clipboards(from_idx, to_idx)
        return True

    def on_toggle_pin(self, btn, type, index):
        if type == "history":
            self.app.history[index]["pinned"] = not self.app.history[index].get("pinned", False)
            self.app.save_history()
        else:
            self.app.clipboards[index]["pinned"] = not self.app.clipboards[index].get("pinned", False)
            self.app.save_clipboards()
        self.refresh_history_ui()

    def on_history_clicked(self, btn):
        self.refresh_history_ui()
        self.history_popover.popup()

    def copy_text_to_clipboard(self, text):
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)
        self.status_label.set_label("Copied to clipboard! 📋")
        self.history_popover.popdown()

    def on_preferences_clicked(self, btn):
        # Switch to settings tab
        self.view_stack.set_visible_child_name("settings")

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
        print("DEBUG: Stopping live session (Key Released)")
        self.orb_btn.remove_css_class("recording")
        self.orb_label.set_label("READY")
        
        # Hide Overlay
        if self.overlay:
            self.overlay.close_overlay()
        
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        
        # We handle history and pasting in wait_and_paste to ensure final buffer is used
        if auto_paste:
            threading.Thread(target=self.wait_and_paste, daemon=True).start()
        else:
            if self.current_transcript:
                self.app.add_to_history(self.current_transcript)
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
        # Wait for transcription worker to finish last chunk
        time.sleep(0.6)
        if self.current_transcript:
            self.app.add_to_history(self.current_transcript)
            GLib.idle_add(self.perform_auto_paste)
        else:
            GLib.idle_add(lambda: self.status_label.set_label("No text captured."))

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
