import os
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

class RecordingOverlay(Gtk.Window):
    """
    A truly transparent, click-through overlay window for GTK4.
    Positions a GIF or image at the bottom-center of the primary monitor.
    """
    def __init__(self, application=None, image_path=None):
        super().__init__(application=application)
        self.set_title("Overlay")
        
        # Internal state for manual GIF playback
        self.anim_iter = None
        self.timeout_id = None
        
        # Make the window strictly non-focusable and click-through
        self.set_can_focus(False)
        self.set_focusable(False)
        self.set_can_target(False)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        
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
        self.content_box.set_margin_bottom(50) 
        self.main_layout.append(self.content_box)
        
        self.img = Gtk.Image()
        self.img.set_pixel_size(200)
        self.content_box.append(self.img)
        
        if image_path:
            self.load_image(image_path)

    def load_image(self, image_path):
        self.stop_animation()
        try:
            if image_path and os.path.exists(image_path):
                anim = GdkPixbuf.PixbufAnimation.new_from_file(image_path)
                if anim.is_static_image():
                    self.img.set_from_file(image_path)
                else:
                    self.anim_iter = anim.get_iter()
                    self.start_animation()
            else:
                self.img.set_from_icon_name("audio-input-microphone-symbols")
        except:
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
