# Shlumzi UI Kit for LibAdwaita

A premium "Deep Amber" theme for GTK4 and LibAdwaita applications. This kit translates the award-winning "Shlumzi" aesthetic into clean, reusable CSS.

## Features
- **Deep Amber Color Palette**: Carefully tuned `#ff7c00` accents.
- **Glassmorphism**: Sleek, semi-transparent panels.
- **Orbital Backgrounds**: Custom radial patterns for that futuristic orbital look.
- **Neon Glows**: Dynamic shadows and glow effects for buttons and interactive elements.

## Installation
Add the contents of `shlumzi.css` to your application's `Gtk.CssProvider`.

## Usage (Python)
```python
css_provider = Gtk.CssProvider()
css_provider.load_from_path("shlumzi.css")
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(), 
    css_provider, 
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
)
```
