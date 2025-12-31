import sys
import os
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, Gdk

class ShlumziWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(800, 600)
        self.set_title("Shlumzi Starter")
        
        # Modern Layout with Adw.ToolbarView
        content = Adw.ToolbarView()
        self.set_content(content)
        
        # Header Bar
        header = Adw.HeaderBar()
        content.add_top_bar(header)
        
        # Main Content
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)
        content.set_content(box)
        
        # Example UI
        label = Gtk.Label(label="Welcome to Shlumzi")
        label.add_css_class("title-1")
        label.add_css_class("status-caption") # From our CSS
        box.append(label)
        
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("glass-view")
        card.append(Gtk.Label(label="This panel uses the glass-view class."))
        card.append(Gtk.Button(label="Neon Action", css_classes=["suggested-action"]))
        box.append(card)
        
        self.load_css()

    def load_css(self):
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(os.path.dirname(__file__), "style.css")
        try:
            css_provider.load_from_path(css_path)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), 
                css_provider, 
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(f"Failed to load CSS: {e}")

class ShlumziApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.ShlumziStarter',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = ShlumziWindow(application=self)
        win.present()

def main():
    app = ShlumziApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
