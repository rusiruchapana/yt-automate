from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import uuid
from pathlib import Path

from PIL import Image

from .domain import MOODS, Problem, stamp, valid_url

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
MAX_UPLOAD = 200 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 30_000_000


def probe(path):
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True, timeout=25, check=True,
        )
        return json.loads(p.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        raise Problem("This media could not be read. Check that FFmpeg is installed and the file is valid.") from e


def inspect_file(path, kind):
    ext = Path(path).suffix.lower()
    if kind == "visual" and ext in IMAGE_EXTS:
        try:
            with Image.open(path) as im:
                if im.width < 100 or im.height < 100:
                    raise Problem("Use an image at least 100 pixels wide and tall.")
                im.verify()
        except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
            raise Problem("Invalid or excessively large image.") from e
        return 0.0
    if (kind == "music" and ext not in AUDIO_EXTS) or (kind == "visual" and ext not in VIDEO_EXTS):
        raise Problem("Unsupported extension. Use JPG/PNG/WebP/MP4/MOV/WebM/MKV for visuals or MP3/WAV/M4A/OGG/FLAC for music.")
    info = probe(path)
    types = {s.get("codec_type") for s in info.get("streams", [])}
    if (kind == "music" and "audio" not in types) or (kind == "visual" and "video" not in types):
        raise Problem("The file does not contain the expected audio/video stream.")
    try:
        duration = float(info["format"].get("duration", 0))
    except (ValueError, TypeError) as e:
        raise Problem("Media has an invalid duration.") from e
    if not math.isfinite(duration) or not 1 <= duration <= 3600:
        raise Problem("Use media between 1 second and 1 hour long.")
    return duration


def register_file(store, path, title, kind, mood="any", rights_notes="", attribution="", source_url="", enabled=False):
    if kind not in {"visual", "music"} or mood not in MOODS:
        raise Problem("Choose a supported asset kind and mood.")
    title = str(title).strip()
    rights_notes = str(rights_notes).strip()
    if not title or len(title) > 120:
        raise Problem("Asset title is required, up to 120 characters.")
    if enabled and not rights_notes:
        raise Problem("Record the asset's usage permission before enabling it.")
    source_url = valid_url(source_url)
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    sha = digest.hexdigest()
    if store.one("SELECT id FROM assets WHERE sha256=?", (sha,)):
        raise Problem("That exact file is already in the library.")
    duration = inspect_file(path, kind)
    asset_id = uuid.uuid4().hex
    ext = Path(path).suffix.lower()
    destination = store.root / "assets" / (asset_id + ext)
    Path(path).replace(destination)
    try:
        with store.connect() as c:
            c.execute("""INSERT INTO assets(id,title,kind,path,sha256,extension,mood,rights_notes,attribution,
                        source_url,enabled,duration,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (asset_id, title, kind, str(destination.relative_to(store.root)), sha, ext, mood,
                       rights_notes[:2000], str(attribution)[:1500], source_url, bool(enabled), duration, stamp()))
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return asset_id


def patch_asset(store, asset_id, raw):
    row = store.one("SELECT * FROM assets WHERE id=?", (asset_id,))
    if not row:
        raise Problem("Asset not found.")
    values = {k: raw.get(k, row[k]) for k in ("title", "mood", "rights_notes", "attribution", "source_url", "enabled", "start_sec")}
    if not isinstance(values["enabled"], bool):
        values["enabled"] = bool(values["enabled"]) if "enabled" not in raw else None
        if values["enabled"] is None:
            raise Problem("Enabled must be true or false.")
    if not str(values["title"]).strip() or len(str(values["title"])) > 120 or values["mood"] not in MOODS:
        raise Problem("Provide a title and a valid mood.")
    if values["enabled"] and not str(values["rights_notes"]).strip():
        raise Problem("Record permission before enabling this asset.")
    values["source_url"] = valid_url(str(values["source_url"]))
    for name, cap in (("rights_notes", 2000), ("attribution", 1500)):
        values[name] = str(values[name]).strip()[:cap]
    try:
        start = float(values["start_sec"])
    except (ValueError, TypeError) as e:
        raise Problem("Start time must be a number of seconds.") from e
    if not math.isfinite(start) or start < 0 or start >= max(row["duration"], 0.001):
        if start != 0:
            raise Problem("Start time must be within the clip or track.")
    values["start_sec"] = start
    with store.connect() as c:
        columns = ",".join(k + "=?" for k in values)
        c.execute("UPDATE assets SET " + columns + " WHERE id=?", (*values.values(), asset_id))


def relative_asset(store, row):
    path = (store.root / row["path"]).resolve()
    if not path.is_relative_to(store.root / "assets"):
        raise Problem("Invalid asset path.")
    return path
