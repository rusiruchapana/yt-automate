# Purple Local Studio - free local starter

A working local dashboard for creating short English fan videos from your own
or cleared clips, illustrations, scripts and music. Includes music uploads,
video previews, CSV batches and optional private or scheduled YouTube uploads.

No paid AI service, cloud server or GPU is required. Your existing computer,
electricity and internet are still needed. This is an automatic editor and
uploader; it does not invent new AI footage or download BTS music or clips.

## Start on Windows with Docker Desktop

1. Extract the ZIP to a normal folder, for example `C:\PurpleLocalStudio`.
2. Open Docker Desktop and wait until its Linux-container engine is running.
3. Open PowerShell in the folder that contains `compose.yaml`.
4. Run:

```powershell
docker compose up -d --build
```

5. Open **http://localhost:8787** and click **Try the free demo**.
6. Wait for a 12-second preview. You do not need a Google account for this.

The demo is preview-only and cannot be uploaded by the starter. It uses original
abstract visuals and an original tone loop, not actual BTS footage or music.
For a finished video, add your own content and select an appropriate audience.

## Full instructions

Read **GUIDE.md** or the included **Purple_Local_Studio_Full_Guide.pdf** for:

- Windows installation, native Ubuntu setup and troubleshooting.
- Uploading custom music and clips, permission notes and automatic selection.
- Writing distinct scripts and importing up to 168 rows at once.
- Connecting your channel through Google's official Desktop OAuth flow.
- A first private upload and hourly public publication slots.
- Pausing, missed slots, interrupted uploads, backup and restore.

YouTube uploads start **OFF**. Connecting a channel does not enable them. Start
with one private upload. Public scheduling is an explicit per-video choice.
The app's cap is 2 uploads per rolling 24 hours by default, adjustable to 24;
YouTube may apply a lower channel-specific limit.

## Useful commands

```powershell
docker compose logs --tail 80 studio
docker compose stop
docker compose start
docker compose run --rm --service-ports auth
docker compose exec studio python scripts/backup.py
```

Before the connection command, place your own Google **Desktop app** OAuth JSON
at `data/secrets/client_secrets.json`. Open the printed authorization URL on
the same computer. Credentials are stored locally and are never included in
this starter ZIP. Do not share `data`, backups, tokens or populated secrets.

## Native development and verification

Install Python 3.12+, FFmpeg and a standard TrueType font. Then:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787 --workers 1 --no-access-log
```

For the included tests:

```bash
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

The native runtime, image and video rendering, audio output, API workflows,
and queue/recovery logic were checked during preparation. Browser visual
verification was unavailable because the browser could not reach this local
execution environment. Docker is not
installed in the preparation environment, so the Docker image itself was not
built there. Google OAuth and actual uploads require your account and must be
verified with a private test. No live YouTube video was uploaded during testing.

## Scope and operating limits

- Localhost only. Do not expose this unauthenticated dashboard to the internet.
- Single app process and one worker; an OS file lock blocks a second worker.
- 3-6 scenes, 3-10 seconds each, maximum 60 seconds, 720p or 1080p portrait.
- Clip audio is replaced with the selected music. Voiceover is not included.
- Identical normalized scripts are rejected even when titles or music change.
- Exact duplicate detection cannot judge creativity or establish copyright.
- Rendered uploaded MP4 cache expires after 7 days by default. Originals,
  manifests and job records remain; set retention to 0 to keep MP4s.
- Pausing blocks new upload starts. In-flight uploads may finish. Remote
  YouTube schedules continue until you change them in YouTube Studio.

Software: MIT. Original demo graphics and tone loop: CC0. See LICENSE and
ASSET-LICENSE.md. Third-party media and packages retain their own rights.
