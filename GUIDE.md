# Purple Local Studio

## 01. Your free starting system

This guide takes you from an extracted starter folder to a local preview,
custom media library, private test upload and an hourly publishing queue.
It is written for your English-language BTS fan channel and a zero-paid-service
starting budget. Prepared on 15 November 2026.

The application is real, editable source code. Python runs the dashboard and
worker, SQLite stores the catalog, and FFmpeg assembles your videos. You can
use the entire local editing workflow without a Google account or paid AI API.

| Included now | What it does |
| --- | --- |
| Custom music and visuals | Upload audio, images and clips; record permission and required credits. |
| Automatic editing | Combine your scenes with selected visuals, music, text and fades. |
| A preview queue | Render locally, watch, download and approve your videos. |
| CSV batches | Import up to 168 distinct scripts and optionally record batch approval. |
| Optional YouTube delivery | Upload privately or upload privately with a future public publication time. |
| Hourly slots | Space a batch by 60 minutes; configure up to 24 uploads per rolling day. |

You provide the ideas, finished scripts and approved source material. This free
edition does not generate new AI footage, synthesize a member's voice, scrape
social media, fetch songs, or write a never-ending supply of new scripts.
It also does not guarantee views, monetization, copyright clearance or a
24-video channel allowance.

Your own computer, internet and electricity are still required. No cloud VM,
credit-card subscription or paid text/image/video API is part of this setup.
Start with a local demo and then one private upload.

## 02. Prepare your computer and folder

Use a Windows computer that meets Docker Desktop's current requirements. Its
Windows documentation lists WSL 2 and 8 GB system RAM among the prerequisites.
Enable hardware virtualization if Docker reports that it is unavailable.
Docker Desktop has licensing conditions; use it under an applicable free
personal-use license, or use native Linux/Docker Engine as appropriate.

1. Download and extract the complete starter ZIP. Do not run inside the ZIP.
2. Place the extracted project somewhere simple, such as C:\PurpleLocalStudio.
3. Confirm that this folder directly contains compose.yaml, Dockerfile,
   README.md, GUIDE.md, app, scripts and examples.
4. Install Docker Desktop from its official website, choose Linux containers
   and complete its WSL 2 setup. Restart Windows if instructed by the installer.
5. Open Docker Desktop and wait for the engine to report that it is running.
6. Open PowerShell in the project folder. Windows Explorer's address bar can
   open a terminal in the current location.

```powershell
cd C:\PurpleLocalStudio
docker --version
docker compose version
```

If you chose another folder, replace the cd path with yours. For a path with
spaces, put it in double quotes. The example location is not mandatory.

You do not need Node.js, PostgreSQL, AWS, an LLM, n8n or a GPU for this starter.
Do not purchase a server for the first test. Docker downloads its image and
Python packages during the first build, so that step needs internet access.
After installation, editing and rendering your local media work offline.

Official Windows installation reference:
https://docs.docker.com/desktop/setup/install/windows-install/

## 03. Start the dashboard and render a demo

From the folder containing compose.yaml, run:

```powershell
docker compose up -d --build
```

The first build downloads Python, FFmpeg, fonts and application dependencies.
Later starts reuse the built image. Open http://localhost:8787 in a browser on
this same computer. The desktop launcher start-windows.ps1 is optional; the
command above avoids PowerShell script-policy issues.

1. On Create a video, click Try the free demo.
2. The worker creates three original abstract backgrounds and an original
   procedural music loop in your local data folder.
3. It renders a 12-second, 720 x 1280 MP4 with three quiz scenes.
4. Wait for the Latest preview to appear, then play it with the video controls.
5. Open Publishing queue and use Preview & review to inspect the result.
6. Use Download MP4 if you want a local copy of the rendered video.

The demo is deliberately preview-only. Its approval/upload option is disabled.
It is a technical example with abstract artwork, not a finished BTS animation.
The factual demo refers to the official MAP OF THE SOUL: 7 album page.

Uploads are OFF, and no Google connection is required at this stage. The app
shows $0 paid API usage because no paid generation service is implemented.

If the page does not open, check Docker Desktop and run:

```powershell
docker compose ps
docker compose logs --tail 80 studio
```

Only the local loopback address is exposed. Do not change the mapping to a
public interface or put the dashboard behind a public tunnel: this edition has
local request protections but no internet-facing user login.

## 04. Build your visual and music library

Open Media & music. This is the collection the editor can use automatically.
Click a file picker, complete its fields and choose Upload to library.

| Field | How to use it |
| --- | --- |
| File | JPG, JPEG, PNG, WebP, MP4, MOV, WebM or MKV for visuals; MP3, WAV, M4A, OGG or FLAC for music. |
| Title | A short name you will recognize later. |
| Kind | Image or video clip, or Background music. |
| Mood | Any, energetic, calm, emotional or funny. |
| Usage permission | Record who created it and the license/permission covering your intended uploads. |
| Required credit | Paste any attribution that must appear in the video description. |
| Source / license URL | An optional reference for your records; the app never downloads this URL. |
| Allow automatic use | Enable only after you have recorded suitable permission. |

Each upload is limited to 200 MiB and the app's local storage allowance.
Audio/video assets must be between 1 second and 1 hour. Tiny, invalid and
excessively large images are rejected. Exact duplicate files are rejected.

Use Edit on an asset to change its mood, permission or start section in seconds.
A music start section lets the editor begin at an allowed part of a track.
Short audio tracks and clips are looped when needed to fill a scene or video.
The renderer discards a source clip's original audio and uses the chosen track.
This version does not mix a separate voiceover.

For automatic selection, the app prefers enabled music matching the requested
mood and favors less-used tracks. Enabled visual files rotate across scenes.
Choose a particular music track or visual in the single-video form when needed.
For exact scene-by-scene visual choices, put asset IDs in the CSV visual_ids
column, separated with |. IDs are shown on library cards.

## 05. Add free music and handle actual BTS recordings

You have three practical ways to populate the music library without buying a
generation service: upload music you created, use tracks already licensed for
your intended use, or download suitable tracks from YouTube Audio Library.

For Audio Library tracks, open YouTube Studio, choose Audio library, select a
track and download its audio file. If attribution is required, copy the exact
credit into the app's Required credit field. Record the source and applicable
license. These credits are captured in the render manifest and added to the
upload description. Check the track's conditions rather than relying on a
random channel calling its music "copyright free".

Actual BTS recordings are not included. Owning an MP3 or seeing a song inside
the Shorts editor does not by itself authorize mixing that recording into an
MP4 on your computer and uploading it through the API. Use an actual BTS file
in the automatic pool only when you have the necessary permission for that
use. The app records your notes; it cannot establish or purchase those rights.

Eligible songs added within YouTube's Shorts creation tools follow YouTube's
in-product music workflow and its conditions. This starter does not automate
that editor or transfer its licensing to a server-rendered video. For this
first free implementation, use your own or otherwise cleared background music.

References:
https://support.google.com/youtube/answer/3376882
https://support.google.com/youtube/answer/13053317

## 06. Create your first finished video

Return to Create a video. Use your own material and write a distinct script.
Choose a format that matches the actual content: fan quiz, fictional mini-story,
verified fact, original commentary or creator showcase.

1. Write a clear title, up to 100 characters.
2. Enter 3-6 short scene paragraphs, one per line, up to 170 characters each.
3. Set 3-10 seconds per scene. Four scenes at 6 seconds create 24 seconds.
4. Choose music automatically by mood, or pick an enabled track explicitly.
5. Rotate your enabled visuals or select one visual for the whole video.
6. Use Fit full image / clip to preserve the composition. Fill frame center-crops
   to portrait and can cut off faces or text, so check the preview carefully.
7. Quizzes and facts require a factual source URL. Read it yourself; a URL field
   records provenance, not automatic fact checking.
8. Choose the audience based on the actual content. Animation alone does not
   decide whether the video is made for kids.
9. Select Private upload for your first test. Public scheduling comes later.
10. Set the synthetic-media disclosure field when your content requires it.
11. Click Create video. Rendering runs locally in the background.

The result contains your text, the selected music, fades and an unofficial fan
footer. Story videos also carry a fictional-fan-story label. None of these
labels grants rights to third-party footage, artwork or songs.

Use Edit video on an unuploaded queue item to change its script, media choice,
audience or metadata. Saving renders it again and clears its earlier approval.
Already-uploaded videos must be managed in YouTube Studio.

When the queue says Awaiting review, open Preview & review. Check text timing,
legibility, audio, framing, source accuracy, media permission and the audience
choice. Download the MP4 and on-screen-text SRT if useful. The SRT is an
on-screen text transcript, not a voice transcription and not automatically
uploaded as a subtitle track.

Record your review and click Approve video. It becomes Ready. It still will not
upload until you connect your channel and explicitly enable uploads.

## 07. Prepare scripts in a CSV batch

The free edition automates editing from a prepared script list. It stops when
that list is exhausted; it does not recycle old videos to fill empty hours.
You can prepare a day's 24 distinct scripts or up to 168 for a week's plan.

Download the example CSV from the dashboard or open examples/starter-scripts.csv.
The 24-slot planning file is examples/hourly-plan-template.csv. Draft examples
have is_demo=true and cannot be automatically approved or uploaded. Replace
all draft content and set is_demo=false only for your finished scripts.

| CSV column | Meaning |
| --- | --- |
| title / format / mood | Title, one of quiz/story/fact/commentary/showcase, and a supported mood. |
| scene1 ... scene6 | Three to six scene paragraphs. Leave unused scene columns empty. |
| seconds_per_scene / fit | Number from 3 to 10; fit is contain or cover. |
| source_url / description | Factual source when needed and your own description. |
| music_id | Optional exact library music ID; empty chooses automatically. |
| visual_ids | Optional one ID or one ID per scene, separated with the vertical-bar character. |
| delivery / publish_local | private or scheduled; an optional per-row local publication time. |
| audience | general means not made for kids; kids means made for kids; undecided cannot be approved. |
| synthetic / is_demo | true or false. Apply the disclosure honestly; demo rows stay local. |

Save as CSV UTF-8. Spreadsheet software must quote fields containing commas.
Avoid letting it rewrite IDs or dates. In the batch form, select the file.
For scheduled rows without their own time, set First publication time and
Spacing in minutes. Use 60 for hourly slots. The app converts the configured
local timezone into UTC for YouTube.

Leave the review checkbox off to inspect each rendered result first. Once you
have reviewed every finished script and its assets, the checkbox records batch
approval, so each successfully rendered job can proceed without another click.
A bad row, duplicate script or occupied slot rejects the whole batch without a
partial import. The message explains what to fix.

## 08. Create your Google project and Desktop OAuth client

This phase is optional until you want uploads. You need your own Google account
with a YouTube channel and the ability to create a Google developer project.
The local editor does not need Google Cloud compute, a paid trial or an AI key.

1. Open https://console.cloud.google.com/ and select or create a project.
2. In APIs & Services, enable YouTube Data API v3 for that project.
3. Open Google Auth Platform / OAuth consent configuration. Interface labels
   can change; Branding, Audience and Data Access are the relevant areas.
4. Enter a recognizable app name such as Purple Local Studio, your support
   email and the contact information Google requires for your project.
5. For an ordinary personal account, configure an External audience and use
   Testing for this first setup. Add your own Google email as a test user.
6. Add the YouTube upload and read-only scopes used by this starter. Upload
   permission sends videos; read-only permission identifies your channel and
   verifies an existing video during recovery.
7. Create an OAuth client ID with application type Desktop app.
8. Download that client's JSON. Use this downloaded file, not a service-account
   key, API key or Web application OAuth client.
9. Rename the file client_secrets.json and put it in data/secrets within the
   project folder. The first app launch already creates that folder.

```text
data/secrets/client_secrets.json
```

The helper expects the top-level installed object from a Desktop client JSON.
The project comes with no populated credentials and never asks you to paste a
Google password into the dashboard. Authorization occurs on Google's page.

Official upload setup:
https://developers.google.com/youtube/data/guides/uploading_a_video

## 09. Connect the intended YouTube channel

Keep the studio running. Open a second PowerShell window in the same project
folder and run the connection helper as a short-lived container:

```powershell
docker compose run --rm --service-ports auth
```

The auth tool shares your local data folder and exposes only the local callback
port 8765. It prints a Google authorization URL. Open that full URL in a browser
on the SAME computer. The Docker tool cannot open the Windows browser itself.

1. Sign into the Google account you added as a test user.
2. Choose the intended YouTube channel, including the appropriate Brand Account
   when Google offers multiple channels.
3. Read the requested permissions and authorize your own project.
4. A testing/unverified-app screen may appear. Continue only after checking
   that it is your own expected project and account.
5. Google redirects the browser to http://localhost:8765/. The page tells you to
   return to your terminal.
6. The terminal verifies the selected channel and prints its name and ID.
7. Return to YouTube & settings. The connected channel name should appear.

The helper saves data/secrets/youtube-token.json locally. It uses state and
PKCE validation, refreshes access tokens when necessary, and verifies the
recorded channel before uploads. Connecting leaves uploads OFF.

Do not close the helper before the redirect completes. It times out after ten
minutes. If port 8765 is occupied, stop the old helper and try again. Do not
share either JSON file or include your data folder in a public repository.

External OAuth apps in Testing normally receive a refresh token expiring after
seven days for these scopes. For your initial free test, reconnect when needed.
Longer unattended operation needs an appropriate production OAuth setup and
any verification Google requires. Refresh tokens can also be revoked earlier.

Reference: https://developers.google.com/identity/protocols/oauth2/

## 10. Make one private upload work first

Use a finished, non-demo job that you created in section 06. Set delivery to
Private upload, choose the actual audience, render it and approve its preview.
Do not use the technical demo or placeholder scripts for this test.

1. In YouTube & settings, confirm the connected channel name and ID.
2. Set Maximum uploads / rolling 24 hours to 1 for this first test.
3. Enable Allow uploads of approved videos and save.
4. Watch Publishing queue. A Ready job changes to Uploading and then Private
   on YouTube after the API accepts it.
5. Open it through Open on YouTube while signed into your channel, or open
   YouTube Studio and find it under Content.
6. Check playback, title, description, required credits, audience and any
   restrictions YouTube reports. A successful upload is not copyright clearance
   or a promise of monetization.
7. Pause new uploads while making changes to your plan.

The code explicitly requests private status. It does not rely on Google's
default privacy setting. A job becomes publicly scheduled only when you chose
Scheduled public video and supplied a future time.

The uploader preserves a resumable session and sends chunks. It checks server
progress after temporary failures. If the result is uncertain, it pauses new
uploads and asks you to reconcile the saved session instead of blindly making
a second upload. The standard API does not provide this app with a definitive
Content ID clearance check.

Reference: https://developers.google.com/youtube/data/reference/rest/v3/videos

## 11. Enable an hourly plan when your channel allows it

Prepare 24 different finished videos. A useful plan varies its ideas, story
structure, explanations and visual treatment; it does not simply swap songs
or member names across the same content.

1. In Settings, keep timezone Asia/Colombo unless you intentionally use another
   valid IANA timezone. Existing saved slots remain absolute UTC times.
2. Set your desired rolling upload cap, up to 24. YouTube can impose a lower
   channel limit, especially while a channel is new.
3. Use scheduled delivery in the CSV rows and select a first publication time
   at least two hours in the future. Give a large/slow batch more lead time.
4. Set batch spacing to 60 minutes. Rows with an explicit publish_local value
   use that value instead of the shared batch start.
5. Import and review the rendered videos, or record batch approval after you
   have checked all scripts and selected assets.
6. Enable uploads. The app prepares and uploads ahead of the publication time;
   it does not wait until the exact hour to begin rendering.

For example, a 19:00 Asia/Colombo slot is 13:30 UTC. This is an illustration of
conversion, not a claim about the best time for Mexico, Peru, Argentina, the US
or Indonesia. Evaluate actual audience data before changing your timetable.

When the app reaches its rolling cap, ready jobs wait. When a publication slot
is missed or is too close, the job is held as Missed slot. There is no burst of
catch-up posts. Use Schedule to choose a new future time, then approve again.

YouTube defines channel-specific upload limits separately from project API
quota. More uploads do not guarantee more reach; high volumes of repetitive
automatic content can violate platform policies. Your app's duplicate-script
check detects exact normalized matches, not every kind of repetitive content.

References:
https://support.google.com/youtube/answer/10383400
https://support.google.com/youtube/answer/2801973

## 12. Understand pausing, sleep and upload recovery

Pause new uploads prevents another job from starting its upload. It does not
cancel an upload already in progress and does not change videos already
scheduled on YouTube. Change or cancel those remote schedules in YouTube Studio.

Keep Docker Desktop, the studio and your computer running and awake while
rendering and uploading. Closing a browser tab does not stop the container.
Sleep, shutdown, loss of internet or quitting Docker stops local progress.
After YouTube has accepted a scheduled video, its publication can occur while
your computer is off. Test this with a small batch before relying on it.

On Windows, review Settings > System > Power & battery and your plugged-in
sleep settings. Use a suitable personal computer; avoid consuming resources
on company production servers for this project.

| Queue state | What to do |
| --- | --- |
| Render failed | Read the message, fix the source/permissions or resource problem, then Retry. |
| Upload held | Read the error, fix authorization/quota/permission issues, Retry and enable uploads when ready. |
| Check interrupted upload | First check the channel in Studio. Resume/check saved upload checks the existing resumable session; it does not replace it. |
| Video exists in Studio | Use Link / recover and paste the 11-character video ID. The app verifies channel ownership before linking it. |
| Saved session expired | Check Studio. Link the existing video if present. Only after confirming no video was created, use the explicit reset option. |
| Missed slot | Choose a new future slot and approve again. |

A restored or interrupted upload needs careful reconciliation. Starting a
fresh upload before checking Studio can create a duplicate. The app never
automatically resets an unknown session.

## 13. Storage, backups and restoration

Your persistent files live in the project's data folder. Keep that folder when
you stop or rebuild the app. It contains the database, media, rendered outputs,
manifests and local Google credentials. The delivered starter has no user data.

The default soft storage cap is 4096 MiB. Uploads stop before exceeding the
upload allowance; rendering checks storage before starting. It is a soft
application limit, not an operating-system disk quota. Leave working space for
temporary rendering files and maintain enough free disk space on the computer.

By default, uploaded MP4 cache is removed after seven days, based on its upload
date. Only MP4s associated with a known YouTube video ID are eligible. Source
assets, SRT files, manifests and job records are retained. Set retention to 0
to keep MP4s. Clean eligible MP4 cache runs the same cleanup immediately.

Create a consistent SQLite snapshot plus local assets and credentials:

```powershell
docker compose exec studio python scripts/backup.py
```

The backup appears in data/backups. Copy it to a protected external location.
It includes credentials, so keep it private. Full backups include the MP4 cache.
The optional --without-videos flag creates a smaller backup; restored
unuploaded jobs are re-rendered for review, and interrupted upload sessions
need manual reconciliation. Backups exclude earlier backups and temporary work.

To restore a full backup, copy its ZIP outside the data folder first. Stop the
app, rename the old data folder to a unique backup name, and extract the
backup's contents into a new data folder. The database must be directly at
data/studio.sqlite3, not in an extra nested folder. Then start the app.

```powershell
docker compose stop
Rename-Item .\data .\data-before-restore
Expand-Archive .\YOUR-BACKUP.zip -DestinationPath .\data
docker compose start
```

Replace YOUR-BACKUP.zip and choose another rename destination if that backup
folder name already exists. Restored backups have uploads disabled. Check
Google authorization, future slots and any interrupted sessions before enabling.

## 14. Native Ubuntu option and routine commands

You can run directly on a personal Ubuntu machine instead of Docker. This
alternative needs Python 3.12 or newer, a compiler-compatible Python package
environment, FFmpeg and a TrueType font. Package availability depends on your
Ubuntu release; the container path is simpler if your system Python is older.

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg fonts-dejavu-core
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787 --workers 1 --no-access-log
```

Run these from the extracted project folder. Open http://localhost:8787 on that
machine. The native command runs in the foreground; keep the terminal open.
Use Ctrl+C to stop it. On the same machine, with the virtual environment active,
the OAuth helper can open your browser directly:

```bash
python scripts/connect_youtube.py
```

Put the downloaded Desktop OAuth file in data/secrets first. If your Ubuntu
machine is a remote headless server, the localhost browser callback needs a
deliberately configured SSH tunnel. That deployment is outside this local-first
starter; do the first setup on your laptop instead of exposing the dashboard.

For Docker installations, these commands preserve your bind-mounted data:

```powershell
docker compose stop
docker compose start
docker compose logs --tail 80 studio
docker compose up -d --build
```

Only run one app worker against one data folder. The worker lock rejects a
second instance. Do not add multiple uvicorn workers or share this SQLite
folder across multiple computers.

## 15. Troubleshooting and practical boundaries

| Problem | Resolution |
| --- | --- |
| Docker command missing | Install Docker Desktop, open a new terminal and verify docker compose version. |
| Engine unavailable | Start Docker Desktop; complete WSL 2/virtualization setup and any required restart. |
| Port 8787 occupied | Stop the earlier studio instance or identify the process using the port before starting another. |
| No enabled visual/music | Upload a supported file, record permission, then enable it. The demo can seed test assets. |
| Duplicate script | Write a different substantive script; changing title or music does not bypass the check. |
| Invalid media | Use a real supported file, not a renamed extension or a link. Check playback and file size. |
| Text or faces cut off | Shorten scenes, preview portrait framing and use contain instead of cover. |
| OAuth access blocked | Use your own External test-user account, Desktop client and enabled YouTube API. Workspace policies may block access. |
| Callback cannot connect | Keep the auth command running, use the same computer and check port 8765. |
| Authorization expires | Reconnect. External Testing refresh tokens normally expire after seven days. |
| Channel/API limit | Wait for the relevant limit to recover; check Feature eligibility and project quotas. Do not create projects to bypass restrictions. |
| Frozen progress after sleep | Restart the app, inspect job status and use the appropriate render or upload recovery path. |

This is a starter, not a fully autonomous creative agency. It has no paid AI
connector, generative animation, voice synthesis, automatic Spanish/Indonesian
translation, automatic Content ID clearance, analytics optimizer or public user
accounts. English text is burned into the video. Every scene file and music
track must come from your approved collection.

For your BTS channel, identify the channel as a fan channel in its name or
handle. Keep fictional scenes clearly fictional and avoid misleading claims
that members own, endorse or participated in your channel. Rights to official
character artwork, photos, recordings and clips need their own assessment.
Labels and edits do not automatically grant permission.


## 16. Verification and official references

The preparation checks cover actual image-to-video and clip-to-video rendering,
H.264 portrait output, non-silent AAC audio, duration, manifests, timezone
conversion, duplicate prevention, atomic imports, approval rules, upload caps,
missed slots, local request protections and interrupted-upload recovery logic.
The API checks cover media validation, request protections, settings and queue
actions. Browser visual verification was unavailable: the browser could not
reach this local execution environment. Check the dashboard in your own
browser during the demo phase and report any layout issue you encounter.

The native Python application and FFmpeg were executed. Docker is not available
in the preparation environment, so the Docker image was not built there.
Google OAuth and live uploads were not executed: those need your own channel.
Upload recovery was checked with mocked Google responses, including a lost
response after the final upload chunk. Always complete the private test phase.

To run the included verification yourself:

```bash
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

The software is MIT-licensed. Its generated abstract demo artwork and procedural
tone loop are CC0; see ASSET-LICENSE.md. Third-party dependencies and fonts
retain their own licenses.

Official references checked during preparation:

- Docker Windows installation: https://docs.docker.com/desktop/setup/install/windows-install/
- FFmpeg filters: https://ffmpeg.org/ffmpeg-filters.html
- YouTube API upload guide: https://developers.google.com/youtube/data/guides/uploading_a_video
- Video upload method: https://developers.google.com/youtube/data/reference/rest/v3/videos/insert
- Private scheduling and video fields: https://developers.google.com/youtube/data/reference/rest/v3/videos
- Google OAuth and refresh tokens: https://developers.google.com/identity/protocols/oauth2/
- Audio Library: https://support.google.com/youtube/answer/3376882
- Shorts music handling: https://support.google.com/youtube/answer/13053317
- Channel upload limits: https://support.google.com/youtube/answer/10383400
- Spam policy: https://support.google.com/youtube/answer/2801973
- Monetization policies: https://support.google.com/youtube/answer/1311392
- Fan-channel identity: https://support.google.com/youtube/answer/2801947
- Synthetic-content disclosure: https://support.google.com/youtube/answer/14328491
- Demo fact source: https://bts.ibighit.com/eng/discography/detail/map_of_the_soul-7.html

Google interfaces, YouTube policies, quotas and package versions can change.
The links above are the authoritative starting points when a screen differs.
