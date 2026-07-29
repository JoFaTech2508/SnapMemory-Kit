#!/usr/bin/env python3
"""
SnapMemory-Kit
Downloads all Snapchat memories with correct dates and metadata
"""

import os
import sys
import warnings
from pathlib import Path

# Suppress urllib3 SSL warnings on macOS
warnings.filterwarnings('ignore', message='.*OpenSSL.*')

# Auto-install missing dependencies BEFORE importing them
required_packages = {
    'requests': 'requests',
    'bs4': 'beautifulsoup4',
    'tqdm': 'tqdm',
    'PIL': 'Pillow'
}

missing_packages = []
for module, package in required_packages.items():
    try:
        __import__(module)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print(f"Installing required packages: {', '.join(missing_packages)}")
    print("This only needs to happen once...\n")
    import subprocess
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
        print("\nPackages installed successfully!\n")
    except subprocess.CalledProcessError:
        print("\nFailed to install packages automatically.")
        print(f"Please run: pip3 install {' '.join(missing_packages)}\n")
        sys.exit(1)

from modules import legacy_export, bundled_export
from modules.constants import VERSION


def main():
    print("╔════════════════════════════════════════════════════════╗")
    print(f"║              SnapMemory-Kit v{VERSION}                     ║")
    print("╚════════════════════════════════════════════════════════╝")
    print()

    # Snapchat now also exports memories as bundled files with no download
    # links at all (no html/memories_history.html). Same script, same
    # command, just detect which one you have and use the matching path.
    if os.path.exists(legacy_export.HTML_FILE):
        legacy_export.run()
        return

    if bundled_export.has_bundled_export():
        print("No export/html/memories_history.html found, but export/ looks like the newer bundled-files export.")
        print()
        choice = input("Dry run first, to see what would happen? (y/n): ").lower()
        bundled_export.run(dry_run=(choice == 'y'))
        if choice == 'y':
            print("\nDry run complete. Re-run and choose 'n' to actually write files.")
        return

    Path("export").mkdir(exist_ok=True)
    print("No Snapchat export found.")
    print()
    print("Created an 'export' folder next to this script - put your Snapchat")
    print("export inside it (the zip files, or an unzipped html/ folder with")
    print("memories_history.html) - then run this again.")


if __name__ == "__main__":
    main()
