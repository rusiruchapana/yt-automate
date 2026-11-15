from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .domain import Problem, check_assets, stamp
from .media import IMAGE_EXTS, probe, relative_asset


def font(size, bold=False):
    names = (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"] if bold else
             ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"])
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, face, width):
    lines, line = [], ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if draw.textlength(candidate, font=face) <= width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = ""
            for ch in word:
                if draw.textlength(line + ch, font=face) > width and line:
                    lines.append(line)
                    line = ""
                line += ch
    if line:
        lines.append(line)
    return lines


def overlay(path, width, height, title, scene, number, total, fmt, demo=False):
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    margin = int(width * .075)
    # Keep text away from the right-hand Shorts controls and bottom controls.
    usable = width - margin * 2 - int(width * .06)
    draw.rectangle((0, 0, width, int(height * .21)), fill=(13, 10, 24, 215))
    draw.rectangle((0, int(height * .54), width, height), fill=(13, 10, 24, 225))
    label = "LOCAL PREVIEW" if demo else {"story": "FICTIONAL FAN STORY", "quiz": "ARMY QUIZ", "fact": "FAN EXPLAINER", "commentary": "FAN COMMENTARY", "showcase": "CREATOR SHOWCASE"}[fmt]
    draw.text((margin, int(height * .04)), label, font=font(int(width*.023), True), fill=(205, 183, 255))
    title_font = font(int(width * .041), True)
    title_lines = wrap(draw, title, title_font, usable)[:3]
    y = int(height * .085)
    for line in title_lines:
        draw.text((margin, y), line, font=title_font, fill="white")
        y += int(width * .053)
    draw.text((margin, int(height * .575)), f"{number:02d} / {total:02d}", font=font(int(width*.025), True), fill=(192, 155, 255))
    size = int(width * .056)
    while True:
        face = font(size, True)
        lines = wrap(draw, scene, face, usable)
        if len(lines) <= 6 or size <= int(width * .037):
            break
        size -= 2
    if len(lines) > 7:
        raise Problem("A scene cannot fit legibly. Shorten its text.")
    y = int(height * .63)
    for line in lines:
        draw.text((margin, y), line, font=face, fill=(249, 247, 255))
        y += int(size * 1.35)
    draw.text((margin, int(height*.91)), "UNOFFICIAL FAN CONTENT", font=font(int(width*.022)), fill=(187, 181, 203))
    im.save(path)


def run_ffmpeg(args, cwd):
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args],
            cwd=cwd, capture_output=True, timeout=900,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Problem("Rendering could not start or exceeded 15 minutes. Check FFmpeg and try a shorter video.") from e
    if result.returncode:
        # No shell or user filename interpolation; stderr stays local and excludes OAuth files.
        detail = result.stderr.decode(errors="replace")[-1200:]
        raise Problem("FFmpeg could not render this media. " + detail)


def srt_time(seconds):
    milliseconds = int(round(seconds * 1000))
    h, milliseconds = divmod(milliseconds, 3_600_000)
    m, milliseconds = divmod(milliseconds, 60_000)
    s, milliseconds = divmod(milliseconds, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{milliseconds:03d}"


def render(store, job, progress=lambda x: None):
    payload = json.loads(job["content"])
    settings = store.settings()
    if store.used_bytes() > settings["storage_limit_mb"] * 1024**2:
        raise Problem("Storage limit reached. Remove unneeded rendered files before continuing.")
    with store.connect() as c:
        check_assets(c, payload)
        assets = {r["id"]: dict(r) for r in c.execute("SELECT * FROM assets")}
    width = settings["render_width"]
    height = width * 16 // 9
    height -= height % 2
    duration = payload["seconds_per_scene"]
    total = duration * len(payload["scenes"])
    work = store.root / "work" / job["id"]
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    output_dir = store.root / "outputs" / job["id"]
    output_dir.mkdir(exist_ok=True)
    final = output_dir / "video.mp4"
    try:
        for i, scene in enumerate(payload["scenes"]):
            row = assets[payload["visual_ids"][i]]
            source = relative_asset(store, row)
            card = work / f"overlay-{i}.png"
            overlay(card, width, height, payload["title"], scene, i+1, len(payload["scenes"]), payload["format"], bool(job["is_demo"]))
            if row["extension"] in IMAGE_EXTS:
                inputs = ["-loop", "1", "-framerate", "24", "-i", str(source)]
            else:
                inputs = ["-stream_loop", "-1", "-ss", str(row["start_sec"]), "-i", str(source)]
            if payload["fit"] == "cover":
                sizing = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
            else:
                sizing = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x100d1c"
            filt = f"[0:v]{sizing},setsar=1,fps=24[base];[base][1:v]overlay=0:0:shortest=1,fade=t=in:st=0:d=0.18,fade=t=out:st={duration-.18}:d=0.18,format=yuv420p[out]"
            run_ffmpeg([*inputs, "-loop", "1", "-i", str(card), "-filter_complex_threads", "1", "-filter_complex", filt,
                        "-map", "[out]", "-an", "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        "-threads", str(settings["threads"]), "-pix_fmt", "yuv420p", "-movflags", "+faststart", f"segment-{i}.mp4"], work)
            progress(int((i+1) / (len(payload["scenes"])+1) * 90))
        (work / "concat.txt").write_text("".join(f"file 'segment-{i}.mp4'\n" for i in range(len(payload["scenes"]))), encoding="utf-8")
        music = assets[payload["music_id"]]
        music_path = relative_asset(store, music)
        audio = f"volume=0.35,alimiter=limit=0.95,afade=t=in:st=0:d=0.4,afade=t=out:st={total-.6}:d=0.6"
        target = work / "video.mp4"
        run_ffmpeg(["-f", "concat", "-safe", "1", "-i", "concat.txt", "-stream_loop", "-1", "-ss", str(music["start_sec"]),
                    "-i", str(music_path), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-af", audio, "-t", str(total), "-movflags", "+faststart", str(target)], work)
        info = probe(target)
        streams = info.get("streams", [])
        if not any(s.get("codec_name") == "h264" and s.get("width") == width for s in streams) or not any(s.get("codec_type") == "audio" for s in streams):
            raise Problem("Rendered video failed its stream checks.")
        if abs(float(info["format"]["duration"]) - total) > .5:
            raise Problem("Rendered video failed its duration check.")
        target.replace(final)
        srt = "\n\n".join(f"{i+1}\n{srt_time(i*duration)} --> {srt_time((i+1)*duration)}\n{scene}" for i, scene in enumerate(payload["scenes"])) + "\n"
        (output_dir / "onscreen-text.srt").write_text(srt, encoding="utf-8")
        attribution = list(dict.fromkeys(r["attribution"] for r in [assets[x] for x in payload["visual_ids"] + [payload["music_id"]]] if r["attribution"]))
        manifest = {
            "created_at": stamp(), "job_id": job["id"], "title": payload["title"], "is_demo": bool(job["is_demo"]),
            "duration_seconds": total, "width": width, "height": height, "payload": payload,
            "video_sha256": hashlib.sha256(final.read_bytes()).hexdigest(), "attribution": attribution,
            "assets": [{k: assets[x][k] for k in ("id", "title", "sha256", "rights_notes", "attribution", "source_url")} for x in dict.fromkeys(payload["visual_ids"]+[payload["music_id"]])],
        }
        (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        progress(100)
        return str(final.relative_to(store.root))
    finally:
        shutil.rmtree(work, ignore_errors=True)
