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

Place the script in the same folder as your Snapchat export:

```
Your-Folder/
├── html/
│   └── memories_history.html
└── download_memories.py
```

## Usage

```bash
cd /path/to/your/folder
python3 download_memories.py
```

The script will auto-install dependencies on first run.

Choose test mode (5 files) or full download when prompted.

## Output Structure

```
downloaded_memories/
├── final/          # Photos/videos with filters - import this folder
├── no_filters/     # Original unedited versions
└── overlays/       # Filter overlays as transparent PNGs
```

Files are organized by year inside each folder.

## Configuration

Edit the script to change your timezone:

```python
LOCAL_TIMEZONE = ZoneInfo('Europe/Oslo')  # Change this
```

Common timezones: `America/New_York`, `America/Los_Angeles`, `Europe/London`, `Asia/Tokyo`

## Troubleshooting

**Missing HTML file?**
Make sure `html/memories_history.html` exists in your folder.

**Download interrupted?**
Run again - already downloaded files are skipped automatically.

**Wrong dates shown?**
Import to Photos/Google Photos - they'll read the EXIF data correctly.

---

© 2025 JoFaTech2508

