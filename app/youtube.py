"""OAuth refresh and resumable YouTube uploads using Python's standard library.

Resumable URLs are persisted privately. An uncertain upload is never replaced
with a fresh upload automatically. No account calls happen during local rendering.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from .domain import Problem, parse_utc, utcnow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
API = "https://www.googleapis.com/youtube/v3/"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class UploadUncertain(Problem):
    pass


class NetworkFailure(Problem):
    pass


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes


class Transport:
    def request(self, method, url, headers=None, data=None):
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return Response(r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(1024*1024))
        except urllib.error.HTTPError as e:
            return Response(e.code, {k.lower(): v for k, v in e.headers.items()}, e.read(1024*1024))
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise NetworkFailure("A Google request could not finish. Check your connection; upload state is retained.") from e


def decode(response):
    try:
        return json.loads(response.body)
    except (ValueError, UnicodeDecodeError) as e:
        raise Problem("Google returned an unreadable response. Check YouTube Studio before retrying.") from e


def api_error(response):
    reason = "requestRejected"
    try:
        obj = json.loads(response.body)
        reason = obj.get("error", {}).get("errors", [{}])[0].get("reason", reason)
        if not re.fullmatch(r"[A-Za-z0-9_]+", reason):
            reason = "requestRejected"
    except (ValueError, TypeError, IndexError):
        pass
    if reason == "uploadLimitExceeded":
        return Problem("YouTube's channel upload limit was reached. New uploads are paused; wait and check channel eligibility.")
    if reason in {"quotaExceeded", "dailyLimitExceeded"}:
        return Problem("The API quota was reached. New uploads are paused; check the Google project quota.")
    return Problem(f"Google rejected the request (HTTP {response.status}, {reason}). Check the connection and channel settings.")


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + uuid.uuid4().hex + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
        temporary.replace(path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def account_info(store):
    path = store.root / "secrets" / "youtube-token.json"
    if not path.exists():
        return {"connected": False}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return {"connected": bool(obj.get("refresh_token") and obj.get("channel_id")),
                "channel_id": obj.get("channel_id", ""), "channel_title": obj.get("channel_title", "")}
    except (ValueError, OSError):
        return {"connected": False}


def access_token(store, transport):
    path = store.root / "secrets" / "youtube-token.json"
    if not path.exists():
        raise Problem("Connect your channel first with scripts/connect_youtube.py. Local rendering works without it.")
    token = json.loads(path.read_text(encoding="utf-8"))
    if not token.get("refresh_token") or not token.get("channel_id"):
        raise Problem("YouTube connection is incomplete. Run the connection helper again.")
    if float(token.get("expires_at", 0)) < time.time() + 180:
        data = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": token["refresh_token"],
                                       "client_id": token["client_id"], "client_secret": token["client_secret"]}).encode()
        r = transport.request("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, data)
        if r.status != 200:
            raise Problem("YouTube authorization expired or was revoked. Reconnect the channel; new uploads are paused.")
        result = decode(r)
        token["access_token"] = result["access_token"]
        token["expires_at"] = time.time() + int(result.get("expires_in", 3600))
        atomic_json(path, token)
    return token


def get_channel(token, transport):
    r = transport.request("GET", API + "channels?part=id,snippet&mine=true",
                          {"Authorization": "Bearer " + token["access_token"]})
    if r.status != 200:
        raise api_error(r)
    return decode(r).get("items", [])


def make_metadata(job, payload, manifest):
    if job["is_demo"]:
        raise Problem("Demo videos cannot be uploaded by this starter.")
    if payload["audience"] not in {"general", "kids"}:
        raise Problem("Choose the video's actual audience before uploading.")
    description = payload.get("description", "").strip()
    description += "\n\nUnofficial fan-created content. Not affiliated with or endorsed by BTS or BIGHIT MUSIC."
    if payload["format"] == "story":
        description += "\nThis is a fictional fan story, not a report of real events."
    if payload.get("source_url"):
        description += "\nSource for factual context: " + payload["source_url"]
    if manifest.get("attribution"):
        description += "\n\nMedia credits:\n" + "\n".join(manifest["attribution"])
    if len(description.encode("utf-8")) > 5000:
        raise Problem("Description and required credits exceed YouTube's limit. Shorten the description; keep required credits.")
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": payload["audience"] == "kids",
              "containsSyntheticMedia": bool(payload.get("synthetic", False))}
    if job["delivery"] == "scheduled":
        if not job.get("publish_at") or parse_utc(job["publish_at"]) < utcnow() + timedelta(minutes=2):
            raise Problem("This publication slot has passed or is too close. Choose a future slot; it will not be posted late.")
        status["publishAt"] = job["publish_at"]
    return {"snippet": {"title": payload["title"], "description": description.strip(), "categoryId": "24",
                        "defaultLanguage": "en", "tags": ["BTS", "fan content"]}, "status": status}


def session_offset(response, size):
    if response.status in {200, 201}:
        obj = decode(response)
        video_id = obj.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise UploadUncertain("Upload finished without a readable video ID. Check YouTube Studio; do not create a fresh upload.")
        return size, video_id
    if response.status == 308:
        value = response.headers.get("range", "")
        match = re.fullmatch(r"bytes=0-(\d+)", value)
        if value and not match:
            raise UploadUncertain("The upload server returned an unexpected range. Check Studio before retrying.")
        offset = int(match.group(1)) + 1 if match else 0
        if not 0 <= offset <= size:
            raise UploadUncertain("The upload server returned an invalid offset.")
        return offset, None
    if response.status in {404, 410}:
        raise UploadUncertain("The saved upload session is no longer available. Check Studio and link an existing video, or confirm it was not uploaded before resetting.")
    raise api_error(response)


def check_session(transport, url, token, size):
    return transport.request("PUT", url,
                             {"Authorization": "Bearer " + token["access_token"], "Content-Length": "0",
                              "Content-Range": f"bytes */{size}"}, b"")


def upload_video(store, job, checkpoint, progress=lambda n: None, transport=None, sleeper=time.sleep):
    transport = transport or Transport()
    payload = json.loads(job["content"])
    path = (store.root / str(job.get("output") or "")).resolve()
    if not path.is_relative_to(store.root / "outputs") or not path.is_file():
        raise Problem("Rendered MP4 was not found. Do not upload a different file into an existing upload session.")
    manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if manifest.get("video_sha256") != digest:
        raise Problem("Rendered MP4 changed after rendering. Review and render again before uploading.")
    metadata = make_metadata(job, payload, manifest)
    token = access_token(store, transport)
    if not any(c["id"] == token["channel_id"] for c in get_channel(token, transport)):
        raise Problem("Connected Google authorization no longer matches the recorded channel. Reconnect the correct channel.")
    size = path.stat().st_size
    session = job.get("upload_session")
    if not session:
        r = transport.request("POST", UPLOAD,
                              {"Authorization": "Bearer " + token["access_token"], "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"},
                              json.dumps(metadata).encode())
        if r.status not in {200, 201}:
            raise api_error(r)
        session = r.headers.get("location", "")
        parsed = urllib.parse.urlparse(session)
        if parsed.scheme != "https" or parsed.hostname != "www.googleapis.com":
            raise UploadUncertain("Upload initialization did not return the expected Google endpoint.")
        checkpoint(session)
        offset, video_id = 0, None
    else:
        parsed = urllib.parse.urlparse(session)
        if parsed.scheme != "https" or parsed.hostname != "www.googleapis.com":
            raise UploadUncertain("Saved upload endpoint is invalid.")
        offset, video_id = session_offset(check_session(transport, session, token, size), size)
    if video_id:
        return video_id
    failures = 0
    with path.open("rb") as f:
        while True:
            f.seek(offset)
            chunk = f.read(8 * 1024 * 1024)
            try:
                if not chunk:
                    r = check_session(transport, session, token, size)
                else:
                    r = transport.request("PUT", session,
                                          {"Authorization": "Bearer " + token["access_token"], "Content-Type": "video/mp4",
                                           "Content-Length": str(len(chunk)), "Content-Range": f"bytes {offset}-{offset+len(chunk)-1}/{size}"}, chunk)
                if r.status >= 500:
                    raise NetworkFailure("Temporary upload server failure.")
                next_offset, video_id = session_offset(r, size)
                if video_id:
                    progress(100)
                    return video_id
                if next_offset == offset:
                    raise NetworkFailure("The upload server has not advanced yet.")
                offset = next_offset
                progress(min(99, int(offset * 100 / size)))
                failures = 0
            except NetworkFailure:
                failures += 1
                if failures > 4:
                    raise UploadUncertain("The connection was interrupted. Use Resume/check saved upload; a fresh upload was not started.")
                sleeper(min(2**failures, 16))
                try:
                    offset, video_id = session_offset(check_session(transport, session, token, size), size)
                    if video_id:
                        progress(100)
                        return video_id
                except NetworkFailure:
                    continue


def verify_existing_video(store, video_id, transport=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise Problem("Paste the 11-character YouTube video ID, not the full URL.")
    transport = transport or Transport()
    token = access_token(store, transport)
    r = transport.request("GET", API + "videos?part=snippet,status&id=" + video_id,
                          {"Authorization": "Bearer " + token["access_token"]})
    if r.status != 200:
        raise api_error(r)
    items = decode(r).get("items", [])
    if len(items) != 1 or items[0]["snippet"]["channelId"] != token["channel_id"]:
        raise Problem("That video was not found on the connected channel.")
    return items[0]
