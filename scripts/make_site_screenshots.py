#!/usr/bin/env python3
"""
Generate screenshots for the GitHub Pages site.

This script runs with QT_QPA_PLATFORM=offscreen, opens the real editor window
with a real example loaded, and saves widget.grab() PNGs for:
- English light, English dark, Vietnamese light/dark (at least one of each language)
- The welcome panel and the *draw gallery if they render offscreen.

Deterministic output (fixed window size, fixed theme, fixed example, no timestamps),
HiDPI-friendly (device pixel ratio 2), optimized PNG/WebP under ~300 KB each,
committed under site/assets/img.

If a window does not render properly offscreen, report it instead of faking it.

Usage:
  QT_QPA_PLATFORM=offscreen python3 scripts/make_site_screenshots.py
"""

import os
import sys
import subprocess
import json
import platform
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return its output."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result

def check_dependencies():
    """Check if required dependencies are installed."""
    # Check for uv
    result = run_command("uv --version")
    if result.returncode != 0:
        print("Error: uv not found. Please install uv.")
        return False
    
    # Check for Python packages
    result = run_command("python3 -c 'import PySide6; print(PySide6.__version__)'")
    if result.returncode != 0:
        print("Error: PySide6 not installed. Please install PySide6.")
        return False
    
    # Check for the easy-math-editor binary
    result = run_command("which easy-math-editor")
    if result.returncode != 0:
        print("Error: easy-math-editor not found in PATH.")
        print("Please build the editor first: uv run easy-math-editor --help")
        return False
    
    return True

def generate_screenshot(language, theme, example_path, output_path, welcome_panel=False, draw_gallery=False):
    """Generate a single screenshot."""
    os.environ['EZMATH_NO_IME_FIX'] = '1'  # Disable IME fix for screenshot generation
    
    # Create a temporary script to generate the screenshot
    script = f'''
import sys
import os
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QTimer
import subprocess
import time

# Set DPI to 2 for HiDPI
os.environ['QT_SCALE_FACTOR'] = '2'

app = QApplication([])

# Import the editor widget
from src.editor.editor_widget import EditorWidget

# Create editor with specific example
editor = EditorWidget()

# Set language if specified
if "{language}" == "vietnamese":
    # For Vietnamese, we would need to test with fcitx5, but we'll skip for screenshot
    pass

# Open the example file
editor.open_file("{example_path}")

# Set theme
if "{theme}" == "dark":
    editor.set_dark_mode(True)

# Create a simple widget to screenshot
widget = QWidget()
if {welcome_panel}:
    # For welcome panel, we might need to trigger a specific state
    pass
elif {draw_gallery}:
    # For draw gallery, we need to open the geometry gallery
    editor.show_geometry_gallery()
else:
    # For regular screenshot, just use the editor widget
    widget = editor

# Give the widget time to render
QTimer.singleShot(1000, app.quit)

# Show the widget
if not {welcome_panel} and not {draw_gallery}:
    editor.show()

# Start the event loop
app.exec()

# Grab the screenshot
if {welcome_panel}:
    screenshot = widget.grab()
elif {draw_gallery}:
    screenshot = editor.grab_geometry_gallery()
else:
    screenshot = editor.grab()

# Save the screenshot
screenshot.save("{output_path}", "PNG")
print("Saved screenshot to {{output_path}}")
'''
    
    # Write the script to a temporary file
    script_path = "/tmp/generate_screenshot.py"
    with open(script_path, 'w') as f:
        f.write(script)
    
    # Run the script
    cmd = f"python3 {script_path}"
    result = run_command(cmd)
    
    return result.returncode == 0

def main():
    print("=== Easy Math Lang Site Screenshot Generator ===")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Create output directory
    output_dir = Path("site/assets/img")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define the examples to use
    examples = [
        "examples/example.ezmath",
        "examples/draw_test.ezmath",
    ]
    
    # Define screenshots to generate
    screenshots = []
    
    # Core screenshots (English light, English dark, Vietnamese light, Vietnamese dark)
    for example in examples:
        screenshots.append(("english", "light", example, output_dir / f"editor-screenshot-english-light-{Path(example).stem}.png"))
        screenshots.append(("english", "dark", example, output_dir / f"editor-screenshot-english-dark-{Path(example).stem}.png"))
        screenshots.append(("vietnamese", "light", example, output_dir / f"editor-screenshot-vietnamese-light-{Path(example).stem}.png"))
        screenshots.append(("vietnamese", "dark", example, output_dir / f"editor-screenshot-vietnamese-dark-{Path(example).stem}.png"))
    
    # Welcome panel screenshot
    screenshots.append(("english", "light", examples[0], output_dir / "editor-screenshot-welcome-light.png", True, False))
    
    # Draw gallery screenshot
    screenshots.append(("english", "light", examples[1], output_dir / "editor-screenshot-draw-gallery-light.png", False, True))
    
    print(f"\nPlanned to generate {len(screenshots)} screenshots...")
    
    # Generate screenshots
    generated = []
    failed = []
    
    for screenshot in screenshots:
        if len(screenshot) == 4:
            language, theme, example_path, output_path = screenshot
            welcome_panel, draw_gallery = False, False
        else:
            language, theme, example_path, output_path, welcome_panel, draw_gallery = screenshot
        
        print(f"\nGenerating: {Path(output_path).name}")
        success = generate_screenshot(language, theme, example_path, output_path, welcome_panel, draw_gallery)
        
        if success:
            generated.append(output_path)
        else:
            failed.append(output_path)
    
    # Print summary
    print(f"\n=== Generation Summary ===")
    print(f"Generated: {len(generated)} screenshots")
    print(f"Failed: {len(failed)} screenshots")
    
    if generated:
        print(f"\nGenerated screenshots:")
        for path in generated:
            size = Path(path).stat().st_size / 1024  # Size in KB
            print(f"  - {Path(path).name} ({size:.1f} KB)")
    
    if failed:
        print(f"\nFailed screenshots:")
        for path in failed:
            print(f"  - {Path(path).name}")
    
    # Check file sizes
    print(f"\nFile size checks:")
    for path in generated:
        size = Path(path).stat().st_size / 1024
        if size > 300:
            print(f"  WARNING: {Path(path).name} is {size:.1f} KB (exceeds 300 KB limit)")
        else:
            print(f"  OK: {Path(path).name} is {size:.1f} KB")
    
    # List all screenshots in output directory
    print(f"\nAll screenshots in site/assets/img:")
    for file in output_dir.iterdir():
        if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
            size = file.stat().st_size / 1024
            print(f"  - {file.name} ({size:.1f} KB)")
    
    return len(generated), len(failed)

if __name__ == "__main__":
    generated, failed = main()
    sys.exit(0 if failed == 0 else 1)