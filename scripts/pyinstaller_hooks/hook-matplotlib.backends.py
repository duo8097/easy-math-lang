"""Only freeze headless rendering and the dynamically imported SVG exporter."""
hiddenimports = [
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_svg",
]
