from __future__ import annotations

import array
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

os.environ["STUDIO_NO_WORKER"] = "1"
from fastapi.testclient import TestClient
from PIL import Image

from app import demo, render, youtube
from app.domain import (Problem, approve, create_jobs, csv_rows, get_job, local_to_utc,
                        public_job, stamp, utcnow, validate_settings)
from app.main import create_app
from app.media import register_file
from app.store import Store
from app.worker import Worker


class StudioCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = tempfile.TemporaryDirectory()
        cls.base = Store(cls.base_dir.name)
        cls.demo_id = demo.seed(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.base_dir.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        shutil.copytree(self.base.root, self.tmp.name, dirs_exist_ok=True)
        self.store = Store(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def raw(self, suffix="one", **kwargs):
        return {"title": "An original fictional fan story " + suffix, "format": "story",
                "scenes": ["A new story starts here: " + suffix, "An unexpected problem appears.", "The friends find a different answer together."],
                "audience": "general", "seconds_per_scene": 3, **kwargs}

    def ready(self, suffix="one", **kwargs):
        job_id = create_jobs(self.store, [self.raw(suffix, **kwargs)])[0]
        with self.store.connect() as c:
            c.execute("UPDATE jobs SET status='ready' WHERE id=?", (job_id,))
        return job_id

    def fake_upload_files(self, job_id, size=100):
        folder = self.store.root / "outputs" / job_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "video.mp4"
        path.write_bytes(b"x" * size)
        (folder / "manifest.json").write_text(json.dumps({"video_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "attribution": ["Credit required"]}))
        with self.store.connect() as c:
            c.execute("UPDATE jobs SET output=? WHERE id=?", (str(path.relative_to(self.store.root)), job_id))
        youtube.atomic_json(self.store.root / "secrets" / "youtube-token.json", {
            "access_token": "test-access", "refresh_token": "test-refresh", "client_id": "test-client", "client_secret": "test-secret",
            "expires_at": time.time()+3600, "channel_id": "UC_TEST", "channel_title": "Test channel",
        })
        return get_job(self.store, job_id)

    def test_duplicate_script_blocked_even_with_new_title(self):
        create_jobs(self.store, [self.raw()])
        with self.assertRaises(Problem):
            create_jobs(self.store, [{**self.raw(), "title": "Different title, same substance"}])

    def test_batch_is_atomic_on_duplicate(self):
        before = len(self.store.rows("SELECT id FROM jobs"))
        with self.assertRaises(Problem):
            create_jobs(self.store, [self.raw(), self.raw("two"), self.raw()])
        self.assertEqual(len(self.store.rows("SELECT id FROM jobs")), before)

    def test_scheduled_slot_uniqueness(self):
        slot = (utcnow()+timedelta(days=2)).isoformat()
        create_jobs(self.store, [self.raw("one", delivery="scheduled", publish_local=slot)])
        with self.assertRaises(Problem):
            create_jobs(self.store, [self.raw("two", delivery="scheduled", publish_local=slot)])

    def test_timezone_conversion_and_dst(self):
        self.assertEqual(stamp(local_to_utc("2030-01-01T19:00", "Asia/Colombo")), "2030-01-01T13:30:00Z")
        with self.assertRaises(Problem):
            local_to_utc("2027-03-14T02:30", "America/New_York")
        with self.assertRaises(Problem):
            local_to_utc("2026-11-01T01:30", "America/New_York")

    def test_facts_require_source_and_audience_for_preapproval(self):
        with self.assertRaises(Problem):
            create_jobs(self.store, [self.raw(format="fact")])
        with self.assertRaises(Problem):
            create_jobs(self.store, [self.raw(preapproved=True, audience="undecided")])

    def test_demo_cannot_be_approved(self):
        with self.store.connect() as c:
            c.execute("UPDATE jobs SET status='review' WHERE id=?", (self.demo_id,))
        with self.assertRaises(Problem):
            approve(self.store, self.demo_id)

    def test_csv_spacing_and_demo_preapproval(self):
        source = "title,format,scene1,scene2,scene3,delivery,audience,is_demo\nOne,story,Start one,Middle one,End one,scheduled,general,false\nTwo,story,Start two,Middle two,End two,scheduled,general,false\n"
        rows = csv_rows(source, "2030-01-01T19:00", 60, self.store.settings(), True)
        ids = create_jobs(self.store, rows)
        slots = [get_job(self.store, x)["publish_at"] for x in ids]
        self.assertEqual(slots, ["2030-01-01T13:30:00Z", "2030-01-01T14:30:00Z"])
        self.assertTrue(get_job(self.store, ids[0])["preapproved"])
        with self.assertRaises(Problem):
            create_jobs(self.store, [self.raw("demo", preapproved=True, is_demo=True)])

    def test_disabled_asset_prevents_upload_and_pauses_queue(self):
        job_id = self.ready()
        music = json.loads(get_job(self.store, job_id)["content"])["music_id"]
        with self.store.connect() as c:
            c.execute("UPDATE assets SET enabled=0 WHERE id=?", (music,))
        self.store.set_settings({"uploads_enabled": True})
        with patch("app.worker.youtube.upload_video") as remote:
            Worker(self.store).upload_one()
        remote.assert_not_called()
        self.assertEqual(get_job(self.store, job_id)["status"], "upload_error")
        self.assertFalse(self.store.settings()["uploads_enabled"])

    def test_rolling_cap_stops_new_upload(self):
        for suffix in ("a", "b"):
            job_id = self.ready(suffix)
            with self.store.connect() as c:
                c.execute("UPDATE jobs SET status='private',uploaded_at=?,youtube_id=? WHERE id=?", (stamp(utcnow()-timedelta(hours=23)), "test"+suffix, job_id))
        waiting = self.ready("c")
        self.store.set_settings({"uploads_enabled": True, "max_uploads_24h": 2})
        with patch("app.worker.youtube.upload_video") as remote:
            self.assertFalse(Worker(self.store).upload_one())
        remote.assert_not_called()
        self.assertEqual(get_job(self.store, waiting)["status"], "ready")

    def test_past_slot_is_held_without_upload(self):
        job_id = self.ready()
        with self.store.connect() as c:
            c.execute("UPDATE jobs SET delivery='scheduled',publish_at=? WHERE id=?", (stamp(utcnow()-timedelta(hours=1)), job_id))
        self.store.set_settings({"uploads_enabled": True})
        with patch("app.worker.youtube.upload_video") as remote:
            Worker(self.store).upload_one()
        remote.assert_not_called()
        self.assertEqual(get_job(self.store, job_id)["status"], "missed")

    def test_recovery_holds_uncertain_upload(self):
        job_id = self.ready()
        with self.store.connect() as c:
            c.execute("UPDATE jobs SET status='uploading',upload_session='private-url' WHERE id=?", (job_id,))
            c.execute("UPDATE jobs SET status='rendering' WHERE id=?", (self.demo_id,))
        self.store.set_settings({"uploads_enabled": True})
        Worker(self.store).recover()
        self.assertEqual(get_job(self.store, job_id)["status"], "upload_unknown")
        self.assertEqual(get_job(self.store, self.demo_id)["status"], "queued")
        self.assertFalse(self.store.settings()["uploads_enabled"])
        self.assertNotIn("upload_session", public_job(get_job(self.store, job_id)))

    def test_metadata_explicit_private_and_disclosures(self):
        job_id = self.ready(audience="kids", synthetic=True)
        job = get_job(self.store, job_id)
        data = youtube.make_metadata(job, json.loads(job["content"]), {"attribution": ["A credit"]})
        self.assertEqual(data["status"]["privacyStatus"], "private")
        self.assertTrue(data["status"]["selfDeclaredMadeForKids"])
        self.assertTrue(data["status"]["containsSyntheticMedia"])
        self.assertNotIn("publishAt", data["status"])
        self.assertIn("A credit", data["snippet"]["description"])

    def test_network_loss_after_final_chunk_recovers_same_video(self):
        job = self.fake_upload_files(self.ready())
        calls, sessions = [], []

        class Fake:
            def request(inner, method, url, headers=None, data=None):
                calls.append((method, url, data))
                if method == "GET":
                    return youtube.Response(200, {}, b'{"items":[{"id":"UC_TEST"}]}')
                if method == "POST":
                    return youtube.Response(200, {"location": "https://www.googleapis.com/upload/test-session"}, b"")
                if data:
                    raise youtube.NetworkFailure("Response lost after server accepted the final bytes")
                return youtube.Response(200, {}, b'{"id":"abcDEF123_-"}')

        video_id = youtube.upload_video(self.store, job, sessions.append, transport=Fake(), sleeper=lambda n: None)
        self.assertEqual(video_id, "abcDEF123_-")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sum(m == "POST" for m, u, d in calls), 1)
        body = json.loads(next(d for m, u, d in calls if m == "POST"))
        self.assertEqual(body["status"]["privacyStatus"], "private")

    def test_expired_saved_session_never_starts_fresh_upload(self):
        job = self.fake_upload_files(self.ready())
        job["upload_session"] = "https://www.googleapis.com/upload/old-session"
        calls = []

        class Fake:
            def request(inner, method, url, headers=None, data=None):
                calls.append(method)
                if method == "GET":
                    return youtube.Response(200, {}, b'{"items":[{"id":"UC_TEST"}]}')
                return youtube.Response(404, {}, b"{}")

        with self.assertRaises(youtube.UploadUncertain):
            youtube.upload_video(self.store, job, lambda s: None, transport=Fake())
        self.assertNotIn("POST", calls)

    def test_private_loopback_api_csrf_and_upload_validation(self):
        app = create_app(self.store.root, start_worker=False)
        with TestClient(app, base_url="http://localhost:8787") as client:
            state = client.get("/api/state").json()
            token = state["csrf"]
            self.assertEqual(client.post("/api/settings", json={"uploads_enabled": False}).status_code, 403)
            self.assertEqual(client.get("/api/state", headers={"Host": "evil.example"}).status_code, 403)
            headers = {"X-Studio-CSRF": token}
            self.assertEqual(client.post("/api/settings", headers={**headers, "Origin": "https://evil.example"}, json={"uploads_enabled": False}).status_code, 403)
            self.assertEqual(client.post("/api/settings", headers=headers, json={"uploads_enabled": True}).status_code, 400)
            response = client.post("/api/assets", headers=headers,
                                   files={"file": ("pretend.png", b"this is not an image", "image/png")},
                                   data={"title": "Bad upload", "kind": "visual"})
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("upload_session", json.dumps(state))
            self.assertEqual(client.get("/api/jobs/missing/file/video.mp4").status_code, 400)
        self.assertEqual(validate_settings({"max_uploads_24h": 24})["max_uploads_24h"], 24)
        with self.assertRaises(Problem):
            validate_settings({"max_uploads_24h": 25})

    def test_editing_unuploaded_job_resets_approval_and_keeps_identity(self):
        job_id = self.ready()
        app = create_app(self.store.root, start_worker=False)
        with TestClient(app, base_url="http://localhost:8787") as client:
            csrf = client.get('/api/state').json()['csrf']
            response = client.post('/api/jobs/'+job_id+'/edit', headers={'X-Studio-CSRF':csrf},
                                   json=self.raw('revised', audience='kids'))
            self.assertEqual(response.status_code,200,response.text)
            row = get_job(self.store,job_id)
            self.assertEqual(row['status'],'queued')
            self.assertEqual(row['id'],job_id)
            self.assertFalse(row['preapproved'])
            self.assertEqual(json.loads(row['content'])['audience'],'kids')
            with self.store.connect() as c:
                c.execute("UPDATE jobs SET youtube_id='abcDEF123_-',status='private' WHERE id=?", (job_id,))
            rejected=client.post('/api/jobs/'+job_id+'/edit',headers={'X-Studio-CSRF':csrf},json=self.raw('again'))
            self.assertEqual(rejected.status_code,400)

    def test_backup_restores_database_and_sources_with_uploads_off(self):
        import zipfile
        self.store.set_settings({'uploads_enabled':True})
        job_id=self.ready('backup')
        project=Path(__file__).resolve().parents[1]
        env={**os.environ,'STUDIO_DATA':str(self.store.root)}
        subprocess.run([__import__('sys').executable,str(project/'scripts'/'backup.py')],env=env,check=True,capture_output=True)
        archive=next((self.store.root/'backups').glob('*.zip'))
        with tempfile.TemporaryDirectory() as restored:
            with zipfile.ZipFile(archive) as z:
                self.assertIn('studio.sqlite3',z.namelist())
                self.assertTrue(any(n.startswith('assets/') for n in z.namelist()))
                z.extractall(restored)
            recovered=Store(restored)
            self.assertEqual(get_job(recovered,job_id)['title'],get_job(self.store,job_id)['title'])
            self.assertFalse(recovered.settings()['uploads_enabled'])

    def test_worker_lock_blocks_second_instance(self):
        first=Worker(self.store)
        second=Worker(self.store)
        with patch.object(first,'tick'):
            first.start()
            try:
                with self.assertRaises(RuntimeError):
                    second.start()
            finally:
                first.close()

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg integration requires ffmpeg and ffprobe")
    def test_real_image_render_has_audio_duration_and_manifest(self):
        job = get_job(self.store, self.demo_id)
        path = self.store.root / render.render(self.store, job)
        info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        self.assertEqual((video["codec_name"], video["width"], video["height"]), ("h264", 720, 1280))
        self.assertAlmostEqual(float(info["format"]["duration"]), 12, delta=.2)
        audio = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-t", "1", "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"])
        samples = array.array("h")
        samples.frombytes(audio)
        self.assertGreater(math.sqrt(sum(s*s for s in samples)/len(samples)), 50)
        self.assertTrue((path.parent / "onscreen-text.srt").exists())
        self.assertEqual(json.loads((path.parent / "manifest.json").read_text())["video_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg integration requires ffmpeg and ffprobe")
    def test_real_video_clip_render(self):
        clip = self.store.root / "work" / "input.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=purple:s=480x270:r=24", "-t", "1.5", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p", str(clip)], check=True)
        asset = register_file(self.store, clip, "Original test clip", "visual", rights_notes="Original test pattern", enabled=True)
        job_id = create_jobs(self.store, [self.raw("clip", visual_ids=[asset])])[0]
        path = self.store.root / render.render(self.store, get_job(self.store, job_id))
        info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(path)]))
        self.assertAlmostEqual(float(info["format"]["duration"]), 9, delta=.2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
