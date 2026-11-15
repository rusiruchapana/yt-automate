from __future__ import annotations

import hmac
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import demo, youtube
from .domain import (Problem, approve, check_assets, create_jobs, csv_rows, event, get_job,
                     local_to_utc, prepare_payload, public_job, stamp, utcnow, validate_settings)
from .maintenance import cleanup_outputs
from .media import MAX_UPLOAD, patch_asset, register_file, relative_asset
from .store import Store
from .worker import Worker

PROJECT = Path(__file__).resolve().parents[1]


def create_app(root=None, start_worker=True):
    store = Store(root or os.environ.get("STUDIO_DATA", PROJECT / "data"))
    worker = Worker(store)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker and os.environ.get("STUDIO_NO_WORKER") != "1":
            worker.start()
        yield
        worker.close()

    app = FastAPI(title="Purple Local Studio", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.store = store
    app.state.worker = worker

    @app.exception_handler(Problem)
    async def problem_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_handler(request, exc):
        return JSONResponse({"detail": "That script, file, video ID or publication slot already exists."}, status_code=409)

    @app.middleware("http")
    async def local_only(request, call_next):
        host = request.headers.get("host", "").lower()
        hostname = urlparse("http://" + host).hostname
        if hostname not in {"localhost", "127.0.0.1", "::1"}:
            return JSONResponse({"detail": "This starter is available on localhost only."}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc.lower() != host:
                return JSONResponse({"detail": "Cross-origin request blocked."}, status_code=403)
            if not hmac.compare_digest(request.headers.get("x-studio-csrf", ""), store.settings()["csrf"]):
                return JSONResponse({"detail": "Refresh the local page and try again."}, status_code=403)
            try:
                if int(request.headers.get("content-length", "0")) > MAX_UPLOAD + 1024*1024:
                    return JSONResponse({"detail": "Upload exceeds 200 MiB."}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid content length."}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.mount("/static", StaticFiles(directory=PROJECT / "app" / "static"), name="static")

    @app.get("/")
    def index():
        return FileResponse(PROJECT / "app" / "static" / "index.html")

    @app.get("/health")
    def health():
        return {"ok": True, "ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe")),
                "worker": bool(worker.thread and worker.thread.is_alive())}

    @app.get("/api/state")
    def state():
        settings = store.settings()
        csrf = settings.pop("csrf")
        rows = store.rows("SELECT * FROM jobs ORDER BY created_at DESC,id DESC LIMIT 300")
        assets = store.rows("SELECT id,title,kind,extension,mood,rights_notes,attribution,source_url,enabled,start_sec,duration,created_at FROM assets ORDER BY created_at DESC,id")
        counts = {r["status"]: r["n"] for r in store.rows("SELECT status,COUNT(*) n FROM jobs GROUP BY status")}
        return {"settings": settings, "csrf": csrf, "jobs": [public_job(r) for r in rows], "assets": assets,
                "counts": counts, "used_bytes": store.used_bytes(), "account": youtube.account_info(store),
                "events": store.rows("SELECT * FROM events ORDER BY id DESC LIMIT 30"), "now_utc": stamp()}

    @app.post("/api/demo")
    def seed_demo():
        return {"id": demo.seed(store)}

    @app.post("/api/jobs")
    async def new_job(request: Request):
        raw = await request.json()
        if not isinstance(raw, dict):
            raise Problem("Provide a video object.")
        return {"ids": create_jobs(store, [raw])}

    @app.post("/api/import")
    async def import_csv(file: UploadFile = File(...), start_local: str = Form(""),
                         interval_minutes: int = Form(60), reviewed: str = Form("false")):
        try:
            data = await file.read(1024*1024+1)
            if len(data) > 1024*1024:
                raise Problem("CSV must be smaller than 1 MiB.")
            try:
                decoded = data.decode("utf-8-sig")
            except UnicodeDecodeError as e:
                raise Problem("Save the CSV as UTF-8.") from e
            rows = csv_rows(decoded, start_local, interval_minutes, store.settings(), reviewed == "true")
            return {"ids": create_jobs(store, rows)}
        finally:
            await file.close()

    @app.post("/api/assets")
    async def add_asset(file: UploadFile = File(...), title: str = Form(...), kind: str = Form(...),
                        mood: str = Form("any"), rights_notes: str = Form(""), attribution: str = Form(""),
                        source_url: str = Form(""), enabled: str = Form("false")):
        extension = Path(file.filename or "").suffix.lower()
        temporary = store.root / "work" / (uuid.uuid4().hex + extension)
        used = store.used_bytes()
        limit = store.settings()["storage_limit_mb"] * 1024**2
        size = 0
        try:
            with temporary.open("wb") as f:
                while chunk := await file.read(1024*1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD or used + size > limit:
                        raise Problem("File exceeds 200 MiB or the local storage allowance. Check settings and cached outputs.")
                    f.write(chunk)
            if not size:
                raise Problem("This file is empty.")
            asset_id = register_file(store, temporary, title, kind, mood, rights_notes, attribution, source_url, enabled == "true")
            return {"id": asset_id}
        finally:
            temporary.unlink(missing_ok=True)
            await file.close()

    @app.patch("/api/assets/{asset_id}")
    async def update_asset(asset_id: str, request: Request):
        patch_asset(store, asset_id, await request.json())
        return {"ok": True}

    @app.get("/api/assets/{asset_id}/file")
    def asset_file(asset_id: str):
        row = store.one("SELECT * FROM assets WHERE id=?", (asset_id,))
        if not row:
            raise Problem("Asset not found.")
        return FileResponse(relative_asset(store, row))

    @app.get("/api/jobs/{job_id}/file/{name}")
    def job_file(job_id: str, name: str, download: bool = False):
        row = get_job(store, job_id)
        if name not in {"video.mp4", "onscreen-text.srt", "manifest.json"}:
            raise Problem("Unsupported download.")
        path = (store.root / "outputs" / job_id / name).resolve()
        if not path.is_relative_to(store.root / "outputs") or not path.is_file():
            raise Problem("File is not available. Rendering may still be running, or the MP4 cache was cleaned.")
        return FileResponse(path, filename=(name if download else None), media_type=("video/mp4" if name.endswith("mp4") else None))

    @app.post("/api/jobs/{job_id}/approve")
    async def approve_job(job_id: str, request: Request):
        if (await request.json()).get("reviewed") is not True:
            raise Problem("Preview the video and confirm that you reviewed it.")
        approve(store, job_id)
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/edit")
    async def edit_job(job_id: str, request: Request):
        raw = await request.json()
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["status"] not in {"queued", "review", "ready", "render_error", "missed", "cancelled"} or row["upload_session"] or row["youtube_id"]:
                raise Problem("Only an unuploaded, inactive job can be edited. Manage remote videos in YouTube Studio.")
            raw["is_demo"] = bool(row["is_demo"])
            raw["preapproved"] = False
            payload, fingerprint, delivery, publish, demo_flag, _ = prepare_payload(c, raw, store.settings())
            c.execute("UPDATE jobs SET title=?,content=?,fingerprint=?,delivery=?,publish_at=?,status='queued',preapproved=0,output=NULL,error='',progress=0,updated_at=? WHERE id=?",
                      (payload["title"], json.dumps(payload), fingerprint, delivery, publish, stamp(), job_id))
            shutil.rmtree(store.root / "outputs" / job_id, ignore_errors=True)
            event(c, job_id, "Edited locally. Re-rendering; review the new result before uploading.")
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/retry")
    def retry(job_id: str):
        row = get_job(store, job_id)
        if row["status"] not in {"render_error", "upload_error", "upload_unknown"}:
            raise Problem("Only a failed or interrupted job can be retried.")
        status = "queued" if row["status"] == "render_error" else "ready"
        with store.connect() as c:
            c.execute("UPDATE jobs SET status=?,error='',progress=0,updated_at=? WHERE id=?", (status, stamp(), job_id))
            event(c, job_id, "Retry requested. Any saved upload session will be checked and resumed, not replaced.")
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        row = get_job(store, job_id)
        if row["status"] not in {"queued", "review", "ready", "render_error", "missed", "upload_error"} or row["upload_session"] or row["youtube_id"]:
            raise Problem("This job cannot be cancelled locally. Manage any remote scheduled video in YouTube Studio.")
        with store.connect() as c:
            c.execute("UPDATE jobs SET status='cancelled',updated_at=? WHERE id=?", (stamp(), job_id))
            event(c, job_id, "Cancelled locally. No remote video was changed.")
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/schedule")
    async def reschedule(job_id: str, request: Request):
        row = get_job(store, job_id)
        if row["status"] not in {"queued", "review", "ready", "render_error", "missed"} or row["upload_session"] or row["youtube_id"]:
            raise Problem("Change remote schedules in YouTube Studio. Only unuploaded jobs can be changed here.")
        raw = await request.json()
        delivery = raw.get("delivery", "private")
        if delivery not in {"private", "scheduled"}:
            raise Problem("Choose private or scheduled.")
        publish = None
        if delivery == "scheduled":
            dt = local_to_utc(raw.get("publish_local", ""), store.settings()["timezone"])
            if dt < utcnow()+timedelta(minutes=10):
                raise Problem("Choose a publication slot at least 10 minutes ahead.")
            publish = stamp(dt)
        next_status = "review" if row["output"] else ("queued" if row["status"] != "render_error" else "render_error")
        with store.connect() as c:
            c.execute("UPDATE jobs SET delivery=?,publish_at=?,status=?,preapproved=0,error='',updated_at=? WHERE id=?",
                      (delivery, publish, next_status, stamp(), job_id))
            event(c, job_id, "Local schedule changed; approve again before uploading.")
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/link")
    async def link_existing(job_id: str, request: Request):
        row = get_job(store, job_id)
        if row["status"] not in {"upload_unknown", "upload_error"}:
            raise Problem("Linking is only available for an interrupted upload.")
        obj = youtube.verify_existing_video(store, (await request.json()).get("video_id", ""))
        status = "scheduled" if obj["status"].get("publishAt") else ("published" if obj["status"]["privacyStatus"] == "public" else "private")
        with store.connect() as c:
            c.execute("UPDATE jobs SET youtube_id=?,status=?,uploaded_at=?,error='',updated_at=? WHERE id=?", (obj["id"], status, stamp(), stamp(), job_id))
            event(c, job_id, "Linked an existing video after checking that it belongs to the connected channel.")
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/reset-session")
    async def reset_session(job_id: str, request: Request):
        row = get_job(store, job_id)
        if row["status"] != "upload_unknown" or (await request.json()).get("confirmed_no_video") is not True:
            raise Problem("Check YouTube Studio and explicitly confirm that no video was created before resetting.")
        with store.connect() as c:
            c.execute("UPDATE jobs SET upload_session=NULL,status='ready',error='',progress=0 WHERE id=?", (job_id,))
            event(c, job_id, "Operator confirmed no remote video exists and explicitly reset the upload session.")
        return {"ok": True}

    @app.post("/api/settings")
    async def settings(request: Request):
        values = validate_settings(await request.json())
        if values.get("uploads_enabled"):
            if not youtube.account_info(store)["connected"]:
                raise Problem("Connect your YouTube channel before enabling uploads.")
            if store.one("SELECT id FROM jobs WHERE status='upload_unknown' LIMIT 1"):
                raise Problem("Resolve interrupted uploads before enabling the queue again.")
        store.set_settings(values)
        return {"ok": True}

    @app.post("/api/cleanup")
    def cleanup():
        return {"removed_bytes": cleanup_outputs(store, store.settings()["retention_days"])}

    @app.get("/api/examples/{name}")
    def examples(name: str):
        if name not in {"starter-scripts.csv", "hourly-plan-template.csv"}:
            raise Problem("Example not found.")
        return FileResponse(PROJECT / "examples" / name, filename=name, media_type="text/csv")

    return app


app = create_app()
