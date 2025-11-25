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

1. Clone this repository:
```bash
git clone https://github.com/quake101/CosmosCleaner.git
cd CosmosCleaner
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the application:
```bash
python CosmosCleaner.py
```

1. Click **Browse** to select your root astrophotography folder
2. Click **Start Scan** to search for target folders
3. Review the results and select folders you want to delete
4. Click **Clean Selected Folders** to permanently delete them

**Warning:** Deletion is permanent and cannot be undone!

## Requirements

- Python 3.8 or higher
- PySide6 6.5.0 or higher

## License

This project is licensed under the MIT License - see the LICENSE file for details.
