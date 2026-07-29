#!/usr/bin/env python3
"""
SnapMemory-Kit - process new export
Matches memories from the new Snapchat export format to their files and organizes them
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image
from tqdm import tqdm

EXPORT_DIR = Path("export")
OUTPUT_DIR = Path("downloaded_memories")
LOCAL_TIMEZONE = ZoneInfo("Europe/Oslo")
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def auto_extract_zips(export_dir):
    """Extract any zip sitting directly in export/ into its own subfolder.
    Checks the zip's own file list against what's already on disk (anywhere
    under export/, regardless of folder name) so it never extracts twice."""
    if not export_dir.exists():
        raise SystemExit(
            f"'{export_dir}/' does not exist. Create it and put your Snapchat "
            f"export (zip files, or the unzipped folders) inside it."
        )

    existing_files = {f.name for f in export_dir.rglob("*") if f.is_file()}

    for zpath in sorted(export_dir.glob("*.zip")):
        with zipfile.ZipFile(zpath) as z:
            names = [Path(n).name for n in z.namelist() if not n.endswith("/")]
            already_extracted = names and all(n in existing_files for n in names)
            if already_extracted:
                continue
            target = export_dir / zpath.stem
            print(f"Extracting {zpath.name} -> {target}/")
            target.mkdir(parents=True, exist_ok=True)
            z.extractall(target)


def find_manifest():
    manifests = list(EXPORT_DIR.rglob("memories_history.json"))
    if not manifests:
        raise SystemExit(
            f"No memories_history.json found under {EXPORT_DIR}/. "
            f"If your export only has html/memories_history.html with download links "
            f"(no raw media files), use download_memories.py instead."
        )
    if len(manifests) > 1:
        raise SystemExit(f"Expected exactly one manifest, found {len(manifests)}: {manifests}")
    manifest = manifests[0]

    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)["Saved Media"]
    if any(item.get("Download Link") or item.get("Media Download Url") for item in data):
        raise SystemExit(
            f"{manifest} has real download links in it - that's the old export "
            f"format. Use download_memories.py instead, not this script."
        )
    return manifest


def load_manifest_entries(manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)["Saved Media"]
    entries = []
    for item in data:
        try:
            utc = datetime.strptime(item["Date"], "%Y-%m-%d %H:%M:%S UTC")
        except ValueError:
            print(f"WARNING: Could not parse date: {item.get('Date')}")
            continue
        lat, lon = None, None
        loc = item.get("Location", "")
        if "Latitude, Longitude:" in loc:
            coords = loc.replace("Latitude, Longitude:", "").strip()
            try:
                lat, lon = map(float, coords.split(","))
            except (ValueError, AttributeError):
                pass
        entries.append({
            "date_utc": utc,
            "media_type": item["Media Type"],
            "latitude": lat,
            "longitude": lon,
        })
    return entries


def index_files_by_guid_and_time(export_dir):
    guid_time = {}
    for zpath in sorted(export_dir.glob("*.zip")):
        with zipfile.ZipFile(zpath) as z:
            for info in z.infolist():
                m = re.search(r"([0-9A-Fa-f-]{36})-main\.", info.filename)
                if m:
                    guid = m.group(1)
                    guid_time.setdefault(guid, datetime(*info.date_time))

    guid_files = defaultdict(dict)  # guid -> {'main': Path, 'overlay': Path}
    for f in export_dir.rglob("*-main.*"):
        m = re.match(r"^\d{4}-\d{2}-\d{2}_([0-9A-Fa-f-]{36})-main\.", f.name)
        if m and "main" not in guid_files[m.group(1)]:
            guid_files[m.group(1)]["main"] = f
    for f in export_dir.rglob("*-overlay.png"):
        m = re.match(r"^\d{4}-\d{2}-\d{2}_([0-9A-Fa-f-]{36})-overlay\.png$", f.name)
        if m and "overlay" not in guid_files[m.group(1)]:
            guid_files[m.group(1)]["overlay"] = f

    # If the zip files got deleted after extraction (e.g. to save disk space),
    # fall back to the extracted file's own mtime, extraction preserves the
    # same timestamp the zip had, just needs reading back as UTC, not local time.
    for guid, files in guid_files.items():
        if guid not in guid_time and "main" in files:
            mtime = files["main"].stat().st_mtime
            guid_time[guid] = datetime.fromtimestamp(mtime, tz=timezone.utc).replace(tzinfo=None)

    return guid_time, guid_files


def match_entries_to_guids(entries, guid_time):
    file_by_second = defaultdict(list)
    for guid, dt in guid_time.items():
        file_by_second[dt].append(guid)

    used = set()
    matches = []
    unresolved = []

    entry_counts = Counter(e["date_utc"] for e in entries)
    entries_by_time = defaultdict(list)
    for e in entries:
        entries_by_time[e["date_utc"]].append(e)

    for t in sorted(entry_counts):
        count = entry_counts[t]
        even_sec = t.second - (t.second % 2)
        candidate_times = sorted({t, t.replace(second=even_sec)}
                                  | ({t.replace(second=even_sec + 2)} if even_sec + 2 < 60 else set()))

        available = []
        for ct in candidate_times:
            available.extend(g for g in file_by_second.get(ct, []) if g not in used)
        available = list(dict.fromkeys(available))

        group_entries = entries_by_time[t]
        if len(available) >= count:
            for entry, guid in zip(group_entries, available[:count]):
                used.add(guid)
                matches.append((entry, guid))
        else:
            unresolved.extend(group_entries)

    return matches, unresolved


def unique_stems_for_matches(matches):
    seen = {}
    result = []
    for entry, guid in matches:
        local = entry["date_utc"].replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TIMEZONE)
        base_stem = local.strftime("%Y-%m-%d_%H%M%S")
        count = seen.get(base_stem, 0)
        seen[base_stem] = count + 1
        stem = base_stem if count == 0 else f"{base_stem}_{count + 1}"
        result.append({**entry, "guid": guid, "date_local": local, "stem": stem})
    return result


def already_backed_up(stem, year):
    # Only final/ counts as "done", a memory that got copied to no_filters/
    # or overlays/ but never finished (e.g. the run was killed mid-way)
    # should still be picked up and completed on the next run.
    loc = OUTPUT_DIR / "final" / year
    return loc.exists() and bool(list(loc.glob(f"{stem}.*")))


def merge_image_with_overlay(main_path, overlay_path, output_path):
    try:
        main_img = Image.open(main_path).convert("RGBA")
        overlay_img = Image.open(overlay_path).convert("RGBA")
        if overlay_img.size != main_img.size:
            overlay_img = overlay_img.resize(main_img.size, Image.Resampling.LANCZOS)
        merged = Image.alpha_composite(main_img, overlay_img)
        if output_path.suffix.lower() in (".jpg", ".jpeg"):
            merged = merged.convert("RGB")
        merged.save(output_path, quality=95)
        return True
    except Exception as e:
        print(f"\nWARNING: Error merging image: {e}")
        return False


def merge_video_with_overlay(main_path, overlay_path, output_path):
    try:
        cmd = ["ffmpeg", "-i", str(main_path), "-i", str(overlay_path),
               "-filter_complex", "[0:v][1:v]overlay=0:0", "-c:a", "copy", "-y", str(output_path)]
        result = subprocess.run(cmd, capture_output=True, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"\nWARNING: Error merging video: {e}")
        return False


def set_exif_data(filepath, item):
    if item["media_type"].lower() != "image":
        return
    exif_date = item["date_local"].strftime("%Y:%m:%d %H:%M:%S")
    cmd = ["exiftool", "-overwrite_original",
           f"-DateTimeOriginal={exif_date}", f"-CreateDate={exif_date}", f"-ModifyDate={exif_date}"]
    if item["latitude"] is not None and item["longitude"] is not None:
        lat, lon = item["latitude"], item["longitude"]
        cmd += [f"-GPSLatitude={abs(lat)}", f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
                f"-GPSLongitude={abs(lon)}", f"-GPSLongitudeRef={'E' if lon >= 0 else 'W'}"]
    cmd.append(str(filepath))
    subprocess.run(cmd, check=False, capture_output=True)


def set_video_creation_time(filepath, item):
    if filepath.suffix.lower() not in VIDEO_EXTENSIONS:
        return
    creation_time = item["date_utc"].strftime("%Y-%m-%dT%H:%M:%SZ")
    temp_path = filepath.with_name(f"{filepath.stem}_meta_tmp{filepath.suffix}")
    cmd = ["ffmpeg", "-y", "-i", str(filepath), "-map_metadata", "0",
           "-metadata", f"creation_time={creation_time}", "-c", "copy", str(temp_path)]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode == 0 and temp_path.exists():
        filepath.unlink()
        temp_path.rename(filepath)
    elif temp_path.exists():
        temp_path.unlink()


def set_file_dates(filepath, local_date):
    timestamp = local_date.timestamp()
    os.utime(filepath, (timestamp, timestamp))


def process_one(item, guid_files, dry_run):
    guid = item["guid"]
    files = guid_files.get(guid, {})
    main_src = files.get("main")
    overlay_src = files.get("overlay")
    if main_src is None:
        return "no_source_file"

    year = item["date_local"].strftime("%Y")
    stem = item["stem"]

    if already_backed_up(stem, year):
        return "already_backed_up"

    if dry_run:
        return "would_process"

    try:
        for folder in ("final", "no_filters", "overlays"):
            (OUTPUT_DIR / folder / year).mkdir(parents=True, exist_ok=True)

        main_dst = OUTPUT_DIR / "no_filters" / year / f"{stem}{main_src.suffix}"
        shutil.copy2(main_src, main_dst)

        final_dst = OUTPUT_DIR / "final" / year / f"{stem}{main_src.suffix}"
        merge_ok = True

        if overlay_src is not None:
            overlay_dst = OUTPUT_DIR / "overlays" / year / f"{stem}{overlay_src.suffix}"
            shutil.copy2(overlay_src, overlay_dst)

            if main_src.suffix.lower() in VIDEO_EXTENSIONS:
                merge_ok = merge_video_with_overlay(main_dst, overlay_dst, final_dst)
            else:
                merge_ok = merge_image_with_overlay(main_dst, overlay_dst, final_dst)
        else:
            shutil.copy2(main_src, final_dst)

        for path in (main_dst, final_dst):
            if path.exists():
                set_exif_data(path, item)
                set_video_creation_time(path, item)
                set_file_dates(path, item["date_local"])
    except Exception as e:
        print(f"\nWARNING: Failed to process {stem}: {e}")
        return "failed"

    return "processed" if merge_ok else "merge_failed"


RESULT_LABELS = {
    "already_backed_up": "Already backed up",
    "processed": "Newly processed",
    "would_process": "Would be processed",
    "merge_failed": "Filter merge failed",
    "failed": "Failed to process",
    "no_source_file": "Listed but no file found",
}


def run(dry_run=True):
    manifest_path = find_manifest()
    entries = load_manifest_entries(manifest_path)

    auto_extract_zips(EXPORT_DIR)
    guid_time, guid_files = index_files_by_guid_and_time(EXPORT_DIR)

    matches, unresolved = match_entries_to_guids(entries, guid_time)
    print(f"Reading export... {len(entries)} memories listed, {len(matches)} have a matching file")

    items = unique_stems_for_matches(matches)

    counts = Counter()
    desc = "Checking" if dry_run else "Processing"
    for item in tqdm(items, unit="file", desc=desc):
        result = process_one(item, guid_files, dry_run)
        counts[result] += 1

    print("\n" + "=" * 50)
    if dry_run:
        print("DRY RUN - downloaded_memories/ untouched")
        print("(zip files in export/ may have been unpacked - that's just")
        print("unpacking your own export, nothing in your backup changed)")
    else:
        print("RUN COMPLETE")
    print("=" * 50)
    for key, n in counts.items():
        print(f"{RESULT_LABELS.get(key, key)}: {n}")

    if unresolved:
        print(f"\nNot found ({len(unresolved)}):")
        for e in unresolved:
            print(f"  {e['date_utc']} UTC  {e['media_type']}")


def has_bundled_export():
    """True if export/ looks like the new (no download-link) export type."""
    if not EXPORT_DIR.exists():
        return False
    return any(EXPORT_DIR.rglob("memories_history.json")) or any(EXPORT_DIR.glob("*.zip"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Actually write files (default is dry-run)")
    args = parser.parse_args()
    run(dry_run=not args.run)
