# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pannellum is a lightweight, free, open-source panorama viewer for the web. Built with vanilla JavaScript and WebGL (~21kB gzipped), it supports equirectangular, cubemap, and multiresolution panorama formats. No frameworks or runtime dependencies. MIT licensed.

**Current version:** 2.5.6 (stored in `VERSION` file)

## Build Commands

Build requires Python 3 and Java (for Closure Compiler, YUI Compressor, HTML Compressor).

```bash
# Development build (outputs to build/)
python3 utils/build/build.py

# Release build
python3 utils/build/build.py release
```

The build merges `src/js/libpannellum.js` + `src/js/pannellum.js`, minifies JS/CSS/HTML, embeds SVG images as data URIs, and generates a standalone `pannellum.htm`. Version string comes from git SHA (dev) or `VERSION` file (release).

## Testing

Tests are Selenium-based visual regression tests comparing screenshots against reference images.

```bash
# Run tests (requires Chrome + ChromeDriver, Selenium, Pillow, NumPy)
python3 tests/run_tests.py

# Run with specific browser
python3 tests/run_tests.py --browser firefox

# Run headless (CI)
xvfb-run -a python3 tests/run_tests.py

# Regenerate reference screenshots
python3 tests/run_tests.py --create-ref
```

Test configuration lives in `tests/tests.html`. Tests verify scene loading, camera movement, zoom, hot spots, and UI layering.

## Code Style

- 4-space indentation
- JSHint validation (no formal config file exists)

## Architecture

Two-layer design with clean separation:

### `src/js/libpannellum.js` — Core WebGL Renderer (~2,000 lines)
Low-level rendering engine handling panorama projection math, WebGL shaders, texture management, and 3D transformations. Supports equirectangular, cubemap, and multiresolution tile-based rendering. Provides a renderer API consumed by the viewer layer.

### `src/js/pannellum.js` — Viewer Controller (~3,400 lines)
High-level viewer managing configuration parsing, user interaction (mouse/touch/keyboard/device orientation), UI components (zoom, fullscreen, compass, load button), hot spot system, scene transitions, auto-rotation, and the public API. Exposes `pannellum.viewer()` constructor.

### `src/standalone/` — Standalone Viewer
Self-contained HTML viewer (`pannellum.htm`) that parses URL parameters to configure the viewer, used for iframe embedding.

### Configuration System
Scene-based JSON configuration with per-panorama settings, global defaults, and URL parameter parsing. Documented in `doc/json-config-parameters.md` and `doc/url-config-parameters.md`.

### Multi-resolution Tile Generator
`utils/multires/generate.py` creates tiled multiresolution panoramas from equirectangular source images using Hugin's `nona` tool.

## CI

GitHub Actions (`.github/workflows/ci.yaml`) runs build + Selenium tests on every push using headless Chrome via xvfb.
