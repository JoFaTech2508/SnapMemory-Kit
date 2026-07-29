# SnapMemory-Kit

Download your Snapchat memories with proper dates, EXIF data, and organized by year.

## Requirements

- Python 3.9 or newer - [Download here](https://www.python.org/downloads/)
- exiftool (for GPS data in photos)
- ffmpeg (for video filter merging)
- Your Snapchat data export (request from [accounts.snapchat.com](https://accounts.snapchat.com/) → My Data)
  - Note: The export can take 24+ hours to be ready for download

### Quick Check

Verify Python is installed:
```bash
python3 --version
```

**macOS users** - Check if Homebrew is installed:
```bash
brew --version
```

If you don't have Homebrew, install it from [brew.sh](https://brew.sh)

### Installing Required Tools

**macOS:**
```bash
brew install exiftool ffmpeg
```

**Windows:**
- Download exiftool from [exiftool.org](https://exiftool.org/)
- Download ffmpeg from [ffmpeg.org](https://ffmpeg.org/download.html)

**Linux:**
```bash
sudo apt install exiftool ffmpeg
```

## Setup

Create an `export` folder next to the script, and put your Snapchat export inside it. Snapchat gives you one of two formats - either works, the script detects which one you have automatically:

**Download-link export:**
```
Your-Folder/
├── export/
│   └── html/
│       └── memories_history.html
└── download_memories.py
```

**Bundled-files export** (the zip files Snapchat gives you, zipped or already unzipped):
```
Your-Folder/
├── export/
│   └── (the zip files, or the unzipped memories/json/html folders)
└── download_memories.py
```

If `export` doesn't exist yet, just run the script once - it creates the folder for you.

## Usage

```bash
cd /path/to/your/folder
python3 download_memories.py
```

The script will auto-install dependencies on first run, then detect your export type automatically.

- Download-link export: choose test mode (5 files) or full download when prompted.
- Bundled-files export: choose dry run first to preview, then run again for real.

## Output Structure

```
downloaded_memories/
├── final/          # Photos/videos with filters - import this folder
├── no_filters/     # Original unedited versions
└── overlays/       # Filter overlays as transparent PNGs
```

Files are organized by year inside each folder.

## Configuration

Edit the timezone in `modules/constants.py`:

```python
LOCAL_TIMEZONE = ZoneInfo("Europe/Oslo")  # Change this
```

Common timezones: `America/New_York`, `America/Los_Angeles`, `Europe/London`, `Asia/Tokyo`

## Troubleshooting

**No Snapchat export found?**
Make sure `export/` contains either `html/memories_history.html`, or the zip files Snapchat gave you.

**Run interrupted?**
Run again - already processed files are skipped automatically.

**Wrong dates shown?**
Import to Photos/Google Photos - they'll read the EXIF data correctly.

---

© 2025 JoFaTech2508

