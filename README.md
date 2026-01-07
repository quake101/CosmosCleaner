# Cosmos Cleaner

A PySide6-based GUI application for scanning and cleaning up astrophotography processing folders.

## Overview

Cosmos Cleaner helps you reclaim disk space by scanning your astrophotography projects for common processing folders (like `calibrated`, `debayered`, `registered`, etc.) and allowing you to selectively delete them. It uses multi-threaded scanning for fast performance even on large directory structures.

## Features

- **Multi-threaded folder scanning** - Fast scanning even on large directory structures
- **Customizable target folders** - Configure which folder names to search for
- **Size calculation** - See how much space each folder is using
- **Selective deletion** - Choose exactly which folders to delete
- **Persistent settings** - Remembers your last scan location and target folder list

## Default Target Folders

The application scans for these folder names by default:
- `calibrated`
- `debayered`
- `logs`
- `registered`
- `fastIntegration`
- `process`

You can customize this list through the Options menu.

## Installation

### Option 1: Download Pre-built Executable (Recommended)

Download the latest executable for your platform from the [Releases](https://github.com/quake101/CosmosCleaner/releases) page:

- **Windows**: `CosmosCleaner.exe` - Double-click to run
- **macOS**: `CosmosCleaner-Mac` - Right-click and select "Open" the first time to bypass Gatekeeper
- **Linux**: `CosmosCleaner-Linux` - Run `chmod +x CosmosCleaner-Linux` then `./CosmosCleaner-Linux`

No Python installation required!

### Option 2: Run from Source

If you prefer to run from source or want to contribute to development:

1. Clone this repository:
```bash
git clone https://github.com/quake101/CosmosCleaner.git
cd CosmosCleaner
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python CosmosCleaner.py
```

**Requirements for running from source:**
- Python 3.8 or higher
- PySide6 6.5.0 or higher

## Usage

1. Click **Browse** to select your root astrophotography folder
2. Click **Start Scan** to search for target folders
3. Review the results and select folders you want to delete
4. Click **Clean Selected Folders** to permanently delete them

**Warning:** Deletion is permanent and cannot be undone!

## License

This project is licensed under the MIT License - see the LICENSE file for details.
