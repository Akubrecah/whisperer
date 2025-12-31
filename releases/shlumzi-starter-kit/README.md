
# Shlumzi Starter Kit

A lightweight template for building premium, modern GTK4/Adwaita applications using Python.
Features the "Shlumzi" aesthetic: Deep Amber accents, orbital glassmorphism, and minimal futuristic UI.

## Getting Started

1. Install dependencies:
   ```bash
   sudo apt install libadwaita-1-dev python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
   pip install .
   ```

2. Run the demo:
   ```bash
   python3 -m shlumzi_starter.app
   ```

## Structure
- `src/shlumzi_starter/style.css`: The core Shlumzi theme.
- `src/shlumzi_starter/app.py`: A `Adw.Application` boilerplate with `Adw.ToolbarView` setup.
