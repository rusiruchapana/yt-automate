from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from datetime import timedelta

from . import render, youtube
from .domain import Problem, check_assets, event, parse_utc, stamp, utcnow
from .maintenance import cleanup_outputs

log = logging.getLogger("purple.worker")


class Worker:
    def __init__(self, store):
        self.store = store
        self.stop = threading.Event()
        self.thread = None
        self.last_cleanup = 0
        self.lock_file = None

    def recover(self):
        with self.store.connect() as c:
            c.execute("UPDATE jobs SET status='queued',progress=0,error='Rendering interrupted; queued again.' WHERE status='rendering'")
            c.execute("UPDATE jobs SET status='upload_unknown',error='Upload was interrupted. Check or resume the saved upload.' WHERE status='uploading'")
            if c.execute("SELECT 1 FROM jobs WHERE status='upload_unknown' LIMIT 1").fetchone():
                c.execute("UPDATE settings SET value='false' WHERE key='uploads_enabled'")

    def start(self):
        self.lock_file = (self.store.root / ".worker.lock").open("a+b")
        self.lock_file.seek(0)
        self.lock_file.write(b"0")
        self.lock_file.flush()
        self.lock_file.seek(0)
        try:
            if __import__('os').name == "nt":
                import msvcrt
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            self.lock_file.close()
            self.lock_file = None
            raise RuntimeError("Another studio worker already uses this data folder. Run only one instance.") from e
        self.recover()
        self.thread = threading.Thread(target=self.loop, name="studio-worker", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=3)
        if self.lock_file and (not self.thread or not self.thread.is_alive()):
            self.lock_file.close()
            self.lock_file = None

    def progress(self, job_id, value):
        with self.store.connect() as c:
            c.execute("UPDATE jobs SET progress=?,updated_at=? WHERE id=?", (value, stamp(), job_id))

    def loop(self):
        while not self.stop.is_set():
            try:
                self.tick()
            except Exception:
                # Keep background failures visible without dumping credentials or resumable URLs.
                log.error("Worker tick failed; inspect the dashboard and local media.")
            self.stop.wait(2)

    def tick(self):
        if time.monotonic() - self.last_cleanup > 3600:
            cleanup_outputs(self.store, self.store.settings()["retention_days"])
            self.last_cleanup = time.monotonic()
        self.upload_one()
        if not self.stop.is_set():
            self.render_one()

    def render_one(self):
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if not row:
                return False
            job = dict(row)
            c.execute("UPDATE jobs SET status='rendering',error='',progress=0,updated_at=? WHERE id=?", (stamp(), job["id"]))
            event(c, job["id"], "Rendering locally; no external API is used.")
        try:
            output = render.render(self.store, job, lambda n: self.progress(job["id"], n))
            status = "ready" if job["preapproved"] and not job["is_demo"] else "review"
            with self.store.connect() as c:
                c.execute("UPDATE jobs SET status=?,output=?,error='',progress=100,updated_at=? WHERE id=?",
                          (status, output, stamp(), job["id"]))
                event(c, job["id"], "Rendered. " + ("Batch approval already recorded." if status == "ready" else "Preview and approve before any upload."))
        except Exception as e:
            message = str(e)[:1500] if isinstance(e, Problem) else "Rendering failed unexpectedly. Check the media and retry."
            with self.store.connect() as c:
                c.execute("UPDATE jobs SET status='render_error',error=?,updated_at=? WHERE id=?", (message, stamp(), job["id"]))
                event(c, job["id"], message)
        return True

    def upload_one(self):
        settings = self.store.settings()
        if not settings["uploads_enabled"]:
            return False
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            count = c.execute("SELECT COUNT(*) FROM jobs WHERE uploaded_at>=?", (stamp(utcnow()-timedelta(hours=24)),)).fetchone()[0]
            if count >= settings["max_uploads_24h"]:
                return False
            row = c.execute("SELECT * FROM jobs WHERE status='ready' ORDER BY COALESCE(publish_at,created_at),id LIMIT 1").fetchone()
            if not row:
                return False
            job = dict(row)
            if job["publish_at"] and parse_utc(job["publish_at"]) < utcnow() + timedelta(minutes=2):
                c.execute("UPDATE jobs SET status='missed',error='Publication slot missed. Select a new future slot; no catch-up upload occurred.' WHERE id=?", (job["id"],))
                event(c, job["id"], "Missed slot held for rescheduling.")
                return True
            try:
                check_assets(c, json.loads(job["content"]))
                if job["is_demo"]:
                    raise Problem("Demo videos are preview-only.")
            except Problem as e:
                c.execute("UPDATE jobs SET status='upload_error',error=? WHERE id=?", (str(e), job["id"]))
                c.execute("UPDATE settings SET value='false' WHERE key='uploads_enabled'")
                return True
            c.execute("UPDATE jobs SET status='uploading',progress=0,error='',updated_at=? WHERE id=?", (stamp(), job["id"]))
            event(c, job["id"], "Starting a private YouTube upload" + (" with a future publication time." if job["delivery"] == "scheduled" else "."))

        def checkpoint(session):
            with self.store.connect() as c:
                c.execute("UPDATE jobs SET upload_session=?,updated_at=? WHERE id=?", (session, stamp(), job["id"]))

        try:
            video_id = youtube.upload_video(self.store, job, checkpoint, lambda n: self.progress(job["id"], n))
            with self.store.connect() as c:
                c.execute("UPDATE jobs SET status=?,youtube_id=?,uploaded_at=?,updated_at=?,progress=100,error='' WHERE id=?",
                          ("scheduled" if job["delivery"] == "scheduled" else "private", video_id, stamp(), stamp(), job["id"]))
                event(c, job["id"], "YouTube accepted the upload. Video ID: " + video_id)
        except Exception as e:
            current = self.store.one("SELECT upload_session FROM jobs WHERE id=?", (job["id"],))
            uncertain = isinstance(e, youtube.UploadUncertain) or bool(current["upload_session"])
            message = str(e)[:1500] if isinstance(e, Problem) else "Upload stopped unexpectedly. Check YouTube Studio before retrying."
            with self.store.connect() as c:
                c.execute("UPDATE jobs SET status=?,error=?,updated_at=? WHERE id=?",
                          ("upload_unknown" if uncertain else "upload_error", message, stamp(), job["id"]))
                c.execute("UPDATE settings SET value='false' WHERE key='uploads_enabled'")
                event(c, job["id"], message)
        return True
