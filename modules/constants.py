from pathlib import Path
from zoneinfo import ZoneInfo

OUTPUT_DIR = Path("downloaded_memories")

# Change timezone if needed: 'America/New_York', 'Europe/London', 'Asia/Tokyo', etc.
LOCAL_TIMEZONE = ZoneInfo("Europe/Oslo")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
