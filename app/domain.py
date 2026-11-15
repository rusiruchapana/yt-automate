from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .store import DEFAULTS, Store

FORMATS = {"quiz", "story", "fact", "commentary", "showcase"}
MOODS = {"any", "energetic", "calm", "emotional", "funny"}
AUDIENCES = {"undecided", "general", "kids"}


class Problem(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def stamp(dt=None):
    return (dt or utcnow()).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def local_to_utc(value: str, zone: str):
    try:
        dt = datetime.fromisoformat(value)
        tz = ZoneInfo(zone)
    except (ValueError, ZoneInfoNotFoundError) as e:
        raise Problem("Use a valid local date/time and IANA timezone.") from e
    if dt.tzinfo:
        return dt.astimezone(timezone.utc)
    aware = dt.replace(tzinfo=tz)
    if aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) != dt:
        raise Problem("That local time does not exist because clocks change. Choose another time.")
    if aware.utcoffset() != dt.replace(tzinfo=tz, fold=1).utcoffset():
        raise Problem("That local time occurs twice. Use a time with an explicit UTC offset.")
    return aware.astimezone(timezone.utc)


def text(value, maximum, name):
    value = str(value or "").strip()
    if not value or len(value) > maximum or any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise Problem(f"{name} is required and must be at most {maximum} characters.")
    return value


def valid_url(value):
    if not value:
        return ""
    if len(value) > 1500 or urlparse(value).scheme not in {"http", "https"} or not urlparse(value).netloc:
        raise Problem("Source must be an http(s) URL. It is recorded, never downloaded automatically.")
    return value


def event(c, job_id, message):
    c.execute("INSERT INTO events(at,job_id,message) VALUES (?,?,?)", (stamp(), job_id, message[:800]))


def get_job(store, job_id):
    row = store.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if row is None:
        raise Problem("Video not found.")
    return row


def public_job(row):
    row = dict(row)
    row.pop("upload_session", None)
    row["content"] = json.loads(row["content"])
    return row


def _choose(c, kind, mood, explicitly=None):
    if explicitly:
        row = c.execute("SELECT * FROM assets WHERE id=? AND kind=?", (explicitly, kind)).fetchone()
        if not row:
            raise Problem(f"Selected {kind} asset was not found.")
        return dict(row)
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM assets WHERE kind=? AND enabled=1 AND rights_notes!='' ORDER BY created_at,id", (kind,))]
    matched = [r for r in rows if r["mood"] in {mood, "any"}]
    rows = matched or rows
    if not rows:
        raise Problem(f"Upload and enable at least one {kind} asset with recorded usage rights first.")
    usage = {}
    for r in c.execute("SELECT content FROM jobs WHERE status!='cancelled' ORDER BY created_at DESC LIMIT 1000"):
        p = json.loads(r["content"])
        for asset_id in p["visual_ids"] + [p["music_id"]]:
            usage[asset_id] = usage.get(asset_id, 0) + 1
    return min(rows, key=lambda r: (usage.get(r["id"], 0), r["created_at"], r["id"]))


def check_assets(c, payload):
    for kind, asset_ids in (("visual", payload["visual_ids"]), ("music", [payload["music_id"]])):
        for asset_id in asset_ids:
            row = c.execute("SELECT * FROM assets WHERE id=? AND kind=?", (asset_id, kind)).fetchone()
            if not row or not row["enabled"] or not row["rights_notes"].strip():
                raise Problem("A selected asset is disabled, missing, or has no recorded permission. Check the library.")


def prepare_payload(c, raw, settings):
    title = text(raw.get("title"), 100, "Title")
    if '<' in title or '>' in title:
        raise Problem("YouTube titles cannot contain angle brackets.")
    fmt = raw.get("format", "quiz")
    mood = raw.get("mood", "any")
    audience = raw.get("audience", "undecided")
    if fmt not in FORMATS or mood not in MOODS or audience not in AUDIENCES:
        raise Problem("Choose a supported format, mood and audience.")
    scenes = raw.get("scenes", [])
    if isinstance(scenes, str):
        scenes = [s.strip() for s in scenes.splitlines() if s.strip()]
    if not isinstance(scenes, list) or not 3 <= len(scenes) <= 6:
        raise Problem("Write 3 to 6 scenes, one paragraph per line.")
    scenes = [text(s, 170, "Each scene") for s in scenes]
    try:
        seconds = float(raw.get("seconds_per_scene", 6))
    except (ValueError, TypeError) as e:
        raise Problem("Scene duration must be a number.") from e
    if not 3 <= seconds <= 10 or len(scenes) * seconds > 60:
        raise Problem("Use 3-10 seconds per scene and no more than 60 seconds overall.")
    fit = raw.get("fit", "contain")
    if fit not in {"contain", "cover"}:
        raise Problem("Choose contain or cover framing.")
    source = valid_url(str(raw.get("source_url", "")).strip())
    if fmt in {"fact", "quiz"} and not source:
        raise Problem("Quizzes and fact videos need a source URL for your review.")
    visual_ids = raw.get("visual_ids", [])
    if isinstance(visual_ids, str):
        visual_ids = [s.strip() for s in visual_ids.split("|") if s.strip()]
    if not visual_ids:
        eligible = [dict(r) for r in c.execute(
            "SELECT * FROM assets WHERE kind='visual' AND enabled=1 AND rights_notes!='' ORDER BY created_at,id")]
        first = _choose(c, "visual", mood)
        visual_ids = [first["id"]] + [r["id"] for r in eligible if r["id"] != first["id"]]
        visual_ids = [visual_ids[i % len(visual_ids)] for i in range(len(scenes))]
    if len(visual_ids) == 1:
        visual_ids *= len(scenes)
    if len(visual_ids) != len(scenes):
        raise Problem("Choose one visual for all scenes or one visual per scene, separated with |.")
    music = _choose(c, "music", mood, raw.get("music_id") or None)
    payload = {
        "title": title, "format": fmt, "mood": mood, "scenes": scenes,
        "seconds_per_scene": seconds, "fit": fit, "source_url": source,
        "description": str(raw.get("description", ""))[:3000],
        "audience": audience, "synthetic": raw.get("synthetic", False) is True,
        "visual_ids": visual_ids, "music_id": music["id"],
    }
    check_assets(c, payload)
    # Music, file changes and titles alone must not bypass duplicate-script detection.
    normalized = "\n".join(re.sub(r"\s+", " ", s).casefold() for s in scenes)
    fingerprint = hashlib.sha256(normalized.encode()).hexdigest()
    delivery = raw.get("delivery", "private")
    if delivery not in {"private", "scheduled"}:
        raise Problem("Choose private upload or scheduled public publication.")
    publish = None
    if delivery == "scheduled":
        value = raw.get("publish_local", "")
        if not value:
            raise Problem("Scheduled videos need a future local publication time.")
        dt = local_to_utc(value, settings["timezone"])
        if dt < utcnow() + timedelta(minutes=10):
            raise Problem("Schedule at least 10 minutes ahead; 2+ hours is better for a large batch.")
        publish = stamp(dt)
    is_demo = raw.get("is_demo", False) is True
    preapproved = raw.get("preapproved", False) is True
    if preapproved and (is_demo or audience == "undecided"):
        raise Problem("Batch approval requires a chosen audience and finished, non-demo scripts.")
    return payload, fingerprint, delivery, publish, is_demo, preapproved


def create_jobs(store: Store, raws):
    if not 1 <= len(raws) <= 168:
        raise Problem("Import between 1 and 168 videos at once.")
    settings = store.settings()
    ids = []
    try:
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            for index, raw in enumerate(raws, 1):
                try:
                    p, fingerprint, delivery, publish, demo, approved = prepare_payload(c, raw, settings)
                    job_id = uuid.uuid4().hex
                    c.execute("""INSERT INTO jobs(id,title,content,fingerprint,status,created_at,updated_at,
                                publish_at,delivery,preapproved,is_demo) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                              (job_id, p["title"], json.dumps(p), fingerprint, "queued", stamp(), stamp(),
                               publish, delivery, approved, demo))
                    event(c, job_id, "Queued for local rendering.")
                    ids.append(job_id)
                except Problem as e:
                    raise Problem(f"Video {index}: {e}") from e
    except sqlite3.IntegrityError as e:
        raise Problem("Nothing imported: a script is duplicated or a publication slot is already reserved.") from e
    return ids


def approve(store, job_id):
    with store.connect() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row or row["status"] != "review":
            raise Problem("Only a rendered video awaiting review can be approved.")
        if row["is_demo"]:
            raise Problem("Demo videos are preview-only. Create your own finished video before uploading.")
        p = json.loads(row["content"])
        if p["audience"] == "undecided":
            raise Problem("Choose the video's audience before rendering your finished version.")
        check_assets(c, p)
        if row["publish_at"] and parse_utc(row["publish_at"]) < utcnow() + timedelta(minutes=10):
            raise Problem("This publication time is too close or has passed. Change its schedule first.")
        c.execute("UPDATE jobs SET status='ready',updated_at=?,error='' WHERE id=?", (stamp(), job_id))
        event(c, job_id, "Approved by the local operator. Waiting for uploads to be enabled.")


def csv_rows(data: str, start_local: str, interval: int, settings, preapproved=False):
    if not 60 <= interval <= 10080:
        raise Problem("Use a batch spacing of at least 60 minutes.")
    reader = csv.DictReader(io.StringIO(data.lstrip("\ufeff")))
    if not reader.fieldnames or "title" not in reader.fieldnames or "scene1" not in reader.fieldnames:
        raise Problem("CSV needs title and scene1 columns. Start with examples/starter-scripts.csv.")
    start = local_to_utc(start_local, settings["timezone"]) if start_local else None
    result = []
    for i, row in enumerate(reader):
        if i >= 168:
            raise Problem("A batch can contain at most 168 videos.")
        if None in row:
            raise Problem("CSV has extra columns. Quote text containing commas.")
        p = {k: (v or "").strip() for k, v in row.items()}
        p["scenes"] = [p.get(f"scene{n}") for n in range(1, 7) if p.get(f"scene{n}")]
        p["synthetic"] = p.get("synthetic", "false").lower() == "true"
        p["is_demo"] = p.get("is_demo", "false").lower() == "true"
        p["preapproved"] = preapproved
        p["seconds_per_scene"] = p.get("seconds_per_scene") or 6
        p["format"] = p.get("format") or "story"
        p["mood"] = p.get("mood") or "any"
        p["audience"] = p.get("audience") or "undecided"
        p["fit"] = p.get("fit") or "contain"
        p["delivery"] = p.get("delivery") or "private"
        if p["delivery"] == "scheduled" and not p.get("publish_local") and start:
            p["publish_local"] = (start + timedelta(minutes=i * interval)).isoformat()
        result.append(p)
    if not result:
        raise Problem("CSV has no video rows.")
    return result


def validate_settings(raw):
    result = {}
    for key in DEFAULTS:
        if key not in raw:
            continue
        value = raw[key]
        if key == "uploads_enabled":
            if not isinstance(value, bool):
                raise Problem("Uploads enabled must be true or false.")
        elif key == "timezone":
            try:
                ZoneInfo(str(value))
            except (ZoneInfoNotFoundError, ValueError) as e:
                raise Problem("Choose a valid IANA timezone, such as Asia/Colombo.") from e
        else:
            if not isinstance(value, int) or isinstance(value, bool):
                raise Problem(f"{key} must be a whole number.")
            ranges = {"max_uploads_24h": (1, 24), "threads": (1, 4), "storage_limit_mb": (256, 102400), "retention_days": (0, 90)}
            if key == "render_width":
                if value not in {720, 1080}:
                    raise Problem("Choose 720 or 1080 pixel output width.")
            elif not ranges[key][0] <= value <= ranges[key][1]:
                raise Problem(f"{key} is outside its permitted range.")
        result[key] = value
    return result
