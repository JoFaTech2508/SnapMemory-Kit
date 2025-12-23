#!/usr/bin/env python3
"""
SnapMemory-Kit v1.0.0
Downloads all Snapchat memories with correct dates and metadata
"""

import os
import sys
import warnings

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

# Now import all required packages
import re
import time
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from tqdm import tqdm
import zipfile
import shutil
import subprocess
from PIL import Image

# Configuration
OUTPUT_DIR = Path("downloaded_memories")
HTML_FILE = "html/memories_history.html"

# Change timezone if needed: 'America/New_York', 'Europe/London', 'Asia/Tokyo', etc.
LOCAL_TIMEZONE = ZoneInfo('Europe/Oslo')


class SnapchatMemoryDownloader:
    def __init__(self, html_file, output_dir):
        self.html_file = html_file
        self.output_dir = Path(output_dir)
        self.memories = []
        self.session = requests.Session()

    def parse_html(self):
        """Parse the HTML file and extract all memories"""
        print("Parsing HTML file...")

        with open(self.html_file, 'r', encoding='utf-8') as f:
            content = f.read()

        soup = BeautifulSoup(content, 'html.parser')
        rows = soup.find_all('tr')

        for row in rows[1:]:  # Skip header row
            cols = row.find_all('td')
            if len(cols) < 4:
                continue

            date_str = cols[0].get_text(strip=True)
            media_type = cols[1].get_text(strip=True)
            location_str = cols[2].get_text(strip=True)

            # Find download link
            link = cols[3].find('a', {'onclick': True})
            if not link:
                continue

            # Extract URL from onclick attribute
            onclick = link.get('onclick', '')
            url_match = re.search(r"downloadMemories\('([^']+)'", onclick)
            if not url_match:
                continue

            url = url_match.group(1)

            # Parse date (format: "2025-12-16 08:59:40 UTC")
            try:
                utc_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S UTC")
                utc_date = utc_date.replace(tzinfo=ZoneInfo('UTC'))
                # Convert to local timezone
                local_date = utc_date.astimezone(LOCAL_TIMEZONE)
            except ValueError:
                print(f"WARNING: Could not parse date: {date_str}")
                continue

            # Parse GPS coordinates
            lat, lon = None, None
            if "Latitude, Longitude:" in location_str:
                coords = location_str.replace("Latitude, Longitude:", "").strip()
                try:
                    lat, lon = map(float, coords.split(','))
                except (ValueError, AttributeError):
                    pass

            memory = {
                'date_utc': utc_date,
                'date_local': local_date,
                'media_type': media_type,
                'latitude': lat,
                'longitude': lon,
                'url': url,
                'date_str': date_str
            }

            self.memories.append(memory)

        print(f"Found {len(self.memories)} memories to download")
        print("=" * 60)
        return self.memories

    def get_file_extension(self, url, media_type):
        """Determine file extension based on URL and media type"""
        # Try to get from URL
        parsed = urlparse(url)
        path = parsed.path
        if '.' in path:
            ext = path.split('.')[-1].lower()
            if ext in ['jpg', 'jpeg', 'png', 'mp4', 'mov']:
                return ext

        # Fallback to media type
        if media_type.lower() == 'image':
            return 'jpg'
        elif media_type.lower() == 'video':
            return 'mp4'
        return 'dat'

    def create_filename(self, memory):
        """Create a filename based on date and time"""
        date = memory['date_local']
        # Format: 2024-12-16_085940
        filename = date.strftime("%Y-%m-%d_%H%M%S")
        ext = self.get_file_extension(memory['url'], memory['media_type'])
        return f"{filename}.{ext}"

    def get_output_path(self, memory):
        """Get the full output path for a memory"""
        date = memory['date_local']
        year = date.strftime("%Y")
        folder = self.output_dir / year
        folder.mkdir(parents=True, exist_ok=True)

        filename = self.create_filename(memory)
        return folder / filename

    def download_file(self, url, output_path):
        """Download a file from URL to output_path"""
        try:
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()

            # Write file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return True
        except Exception as e:
            print(f"\nWARNING: Failed to download: {e}")
            return False

    def extract_if_zip(self, filepath):
        """Extract media files from ZIP if needed (both main and overlay)"""
        temp_dir = None
        try:
            # Get year from original filepath (e.g., "2025")
            year = str(filepath.relative_to(self.output_dir).parent)
            base_filename = filepath.stem  # e.g., "2025-12-16_095940"

            # Create folder structure for each category
            final_folder = self.output_dir / "final" / year
            no_filters_folder = self.output_dir / "no_filters" / year
            overlays_folder = self.output_dir / "overlays" / year

            final_folder.mkdir(parents=True, exist_ok=True)
            no_filters_folder.mkdir(parents=True, exist_ok=True)
            overlays_folder.mkdir(parents=True, exist_ok=True)

            # Check if file is a ZIP
            if not zipfile.is_zipfile(filepath):
                # Not a ZIP - this is a regular file without filters
                # Move it to the final folder (it's the finished version)
                new_path = final_folder / filepath.name
                if new_path.exists():
                    new_path.unlink()
                shutil.move(str(filepath), str(new_path))
                return [new_path]

            # Extract the media files
            temp_dir = filepath.parent / f"_temp_{filepath.stem}"
            temp_dir.mkdir(exist_ok=True)

            extracted_files = []

            with zipfile.ZipFile(filepath, 'r') as zip_ref:
                # Get all files in the ZIP
                files = zip_ref.namelist()

                # Find main media file
                main_file = None
                overlay_file = None

                for f in files:
                    if f.startswith('__MACOSX') or f.startswith('.'):
                        continue

                    if '-main.' in f.lower():
                        main_file = f
                    elif '-overlay.' in f.lower():
                        overlay_file = f

                # If no -main file, take the first non-hidden file
                if not main_file:
                    valid_files = [f for f in files if not f.startswith('__MACOSX') and not f.startswith('.')]
                    if valid_files:
                        main_file = valid_files[0]
                    else:
                        return [filepath]  # No valid files, keep original

                # Extract main file
                main_filepath = None
                if main_file:
                    try:
                        extracted_path = Path(zip_ref.extract(main_file, temp_dir))
                        actual_ext = extracted_path.suffix

                        # Save main file to no_filters folder
                        main_filepath = no_filters_folder / f"{base_filename}{actual_ext}"

                        if main_filepath.exists():
                            main_filepath.unlink()

                        if extracted_path.exists():
                            shutil.move(str(extracted_path), str(main_filepath))
                            extracted_files.append(main_filepath)
                    except Exception as e:
                        print(f"\nWARNING: Error extracting main file: {e}")

                # Extract overlay file if it exists
                overlay_filepath = None
                if overlay_file:
                    try:
                        extracted_path = Path(zip_ref.extract(overlay_file, temp_dir))
                        overlay_ext = extracted_path.suffix

                        # Save overlay to overlays folder
                        overlay_filepath = overlays_folder / f"{base_filename}{overlay_ext}"

                        if overlay_filepath.exists():
                            overlay_filepath.unlink()

                        if extracted_path.exists():
                            shutil.move(str(extracted_path), str(overlay_filepath))
                            extracted_files.append(overlay_filepath)
                    except Exception as e:
                        pass  # Overlay is optional, skip if fails

                # Create final version if we have both main and overlay
                if main_filepath and overlay_filepath and main_filepath.exists() and overlay_filepath.exists():
                    # Save final version to final folder
                    final_filepath = final_folder / f"{base_filename}{main_filepath.suffix}"

                    # Determine if it's a video or image
                    is_video = main_filepath.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv']

                    if is_video:
                        # Merge video with overlay
                        if self.merge_video_with_overlay(main_filepath, overlay_filepath, final_filepath):
                            extracted_files.append(final_filepath)
                    else:
                        # Merge image with overlay
                        if self.merge_image_with_overlay(main_filepath, overlay_filepath, final_filepath):
                            extracted_files.append(final_filepath)

                # Remove the original ZIP file (only if it's different from extracted files)
                # This happens when the guessed extension was wrong
                if filepath.exists():
                    # Check if filepath is one of the extracted files
                    if filepath not in extracted_files:
                        filepath.unlink()

                return extracted_files if extracted_files else [filepath]

        except Exception as e:
            # If extraction fails, keep the original file
            return [filepath]
        finally:
            # Clean up temporary extraction directory
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Clean up empty year folder (e.g., downloaded_memories/2025/)
            year_folder = filepath.parent
            if year_folder.exists():
                try:
                    year_folder.rmdir()  # Only succeeds if empty
                except OSError:
                    pass  # Not empty, keep it

    def set_file_dates(self, filepath, local_date):
        """Set file creation and modification dates"""
        # Convert to timestamp
        timestamp = local_date.timestamp()

        # Check if file exists first
        if not os.path.exists(filepath):
            return  # File doesn't exist, skip silently

        # Set modification and access time
        os.utime(filepath, (timestamp, timestamp))

        # On macOS, also set birth time (creation date)
        if sys.platform == 'darwin':
            try:
                import subprocess
                date_str = local_date.strftime("%m/%d/%Y %H:%M:%S")
                subprocess.run(['SetFile', '-d', date_str, str(filepath)],
                             check=False, capture_output=True)
            except (FileNotFoundError, subprocess.SubprocessError):
                pass  # SetFile not available, skip

    def set_exif_data(self, filepath, memory):
        """Set EXIF data for images using exiftool"""
        if memory['media_type'].lower() != 'image':
            return

        try:
            import subprocess

            date = memory['date_local']

            # Format dates for EXIF
            exif_date = date.strftime("%Y:%m:%d %H:%M:%S")

            commands = [
                'exiftool',
                '-overwrite_original',
                f'-DateTimeOriginal={exif_date}',
                f'-CreateDate={exif_date}',
                f'-ModifyDate={exif_date}',
            ]

            # Add GPS data if available
            if memory['latitude'] and memory['longitude']:
                lat = memory['latitude']
                lon = memory['longitude']

                commands.extend([
                    f'-GPSLatitude={abs(lat)}',
                    f'-GPSLatitudeRef={"N" if lat >= 0 else "S"}',
                    f'-GPSLongitude={abs(lon)}',
                    f'-GPSLongitudeRef={"E" if lon >= 0 else "W"}',
                ])

            commands.append(str(filepath))

            subprocess.run(commands, check=False, capture_output=True)
        except Exception as e:
            # exiftool not available or failed, skip
            pass

    def merge_image_with_overlay(self, main_image_path, overlay_path, output_path):
        """Merge overlay PNG onto main image using PIL"""
        try:
            # Open both images
            main_img = Image.open(main_image_path).convert('RGBA')
            overlay_img = Image.open(overlay_path).convert('RGBA')

            # Resize overlay to match main image size if needed
            if overlay_img.size != main_img.size:
                overlay_img = overlay_img.resize(main_img.size, Image.Resampling.LANCZOS)

            # Composite overlay on top of main image
            merged = Image.alpha_composite(main_img, overlay_img)

            # Convert back to RGB if saving as JPG
            if output_path.suffix.lower() in ['.jpg', '.jpeg']:
                merged = merged.convert('RGB')

            # Save merged image
            merged.save(output_path, quality=95)
            return True
        except Exception as e:
            print(f"\nWARNING: Error merging image: {e}")
            return False

    def merge_video_with_overlay(self, main_video_path, overlay_path, output_path):
        """Merge overlay PNG onto video using ffmpeg"""
        try:
            # ffmpeg command to overlay PNG on video
            cmd = [
                'ffmpeg',
                '-i', str(main_video_path),
                '-i', str(overlay_path),
                '-filter_complex', '[0:v][1:v]overlay=0:0',
                '-c:a', 'copy',  # Copy audio without re-encoding
                '-y',  # Overwrite output file
                str(output_path)
            ]

            result = subprocess.run(cmd, capture_output=True, check=False)
            return result.returncode == 0
        except Exception as e:
            print(f"\nWARNING: Error merging video: {e}")
            return False

    def download_all(self, test_mode=False):
        """Download all memories"""
        if not self.memories:
            self.parse_html()

        memories_to_download = self.memories[:5] if test_mode else self.memories

        print(f"\nStarting download...")
        print(f"Output directory: {self.output_dir.absolute()}\n")

        success_count = 0
        skip_count = 0
        fail_count = 0
        failed_downloads = []  # Track failed downloads for detailed reporting

        with tqdm(total=len(memories_to_download), unit='file',
                  bar_format='{desc}{percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                  desc='Downloading: ') as pbar:
            for memory in memories_to_download:
                output_path = self.get_output_path(memory)

                # Check if file already exists in any of the three folders (much faster than rglob)
                base_name = output_path.stem
                year = memory['date_local'].strftime("%Y")

                # Check the three possible locations where file might exist
                possible_locations = [
                    self.output_dir / "final" / year,
                    self.output_dir / "no_filters" / year,
                    self.output_dir / "overlays" / year,
                    self.output_dir / year  # Original location before extraction
                ]

                file_exists = False
                for location in possible_locations:
                    if location.exists():
                        matching_files = list(location.glob(f"{base_name}.*"))
                        if matching_files:
                            file_exists = True
                            break

                if file_exists:
                    skip_count += 1
                    pbar.update(1)
                    continue

                # Download file
                if self.download_file(memory['url'], output_path):
                    # Extract from ZIP if needed (returns list of files)
                    final_paths = self.extract_if_zip(output_path)

                    # Process each extracted file (main + overlay)
                    for final_path in final_paths:
                        # Set EXIF data for images FIRST (before file dates)
                        # Only set EXIF on main file (not overlay)
                        if '_overlay' not in final_path.stem:
                            self.set_exif_data(final_path, memory)

                        # Set file dates LAST (after EXIF, so they don't get overwritten)
                        self.set_file_dates(final_path, memory['date_local'])

                    success_count += 1
                else:
                    fail_count += 1
                    failed_downloads.append({
                        'date': memory['date_str'],
                        'type': memory['media_type'],
                        'url': memory['url']
                    })

                pbar.update(1)

                # Small delay to avoid rate limiting
                time.sleep(0.1)

        # Clean up any empty year folders
        for year_folder in self.output_dir.iterdir():
            if year_folder.is_dir() and year_folder.name.isdigit():
                if not any(year_folder.iterdir()):
                    year_folder.rmdir()

        print("\n" + "=" * 60)
        print(f"Successfully downloaded: {success_count}")
        print(f"Skipped (already exist): {skip_count}")
        print(f"Failed: {fail_count}")
        
        # Show failed downloads if any
        if failed_downloads:
            print(f"\nFailed downloads:")
            for i, failed in enumerate(failed_downloads[:5], 1):  # Show max 5
                print(f"   {i}. {failed['date']} ({failed['type']})")
            if len(failed_downloads) > 5:
                print(f"   ... and {len(failed_downloads) - 5} more")


def main():
    print("╔════════════════════════════════════════════════════════╗")
    print("║              SnapMemory-Kit v1.0.0                     ║")
    print("╚════════════════════════════════════════════════════════╝")
    print()

    # Check if HTML file exists
    if not os.path.exists(HTML_FILE):
        print(f"ERROR: Could not find {HTML_FILE}")
        return

    downloader = SnapchatMemoryDownloader(HTML_FILE, OUTPUT_DIR)

    # Parse HTML first
    downloader.parse_html()

    # Ask user if they want to test first
    print()
    choice = input("Do you want to test with 5 files first? (y/n): ").lower()

    if choice == 'y':
        downloader.download_all(test_mode=True)
        print("\nTest complete! Check the 'downloaded_memories' folder.")
        print("If everything looks good, run the script again and choose 'n' to download everything.")
    else:
        downloader.download_all(test_mode=False)

    print("\nDone! Files are ready to import.")


if __name__ == "__main__":
    main()
