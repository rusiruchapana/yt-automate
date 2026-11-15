# Verification - 15 November 2026

20 included automated checks passed in the native Python 3.12 environment.
The integration tests invoked FFmpeg 7.1.5 and ffprobe, rendered real MP4 files
from both images and video clips, and measured non-silent audio.

Checked behaviors include:

- Private upload metadata, explicit audience and synthetic-content fields.
- Actual H.264 720 x 1280 output, AAC audio, duration and content hashes.
- Duplicate scripts despite different titles, atomic CSV import and unique slots.
- Asia/Colombo time conversion and rejection of ambiguous/nonexistent DST times.
- Demo-upload prevention, source requirements and batch-approval rules.
- Disabled asset blocking, rolling 24-hour caps and holding missed slots.
- Restart recovery, resumable state and no automatic fresh upload for an
  expired session with an unknown outcome.
- Simulated lost network response after the final bytes: recovered the same
  video ID through the existing session without a second upload request.
- Local request protections, invalid media rejection and disconnected-account
  restrictions.
- Editing invalidates approval; uploaded jobs cannot be edited locally.
- Full backup/restore preserves sources and jobs and restores uploads as OFF.
- Operating-system lock prevents two workers using one data folder.

JavaScript syntax was checked with Node.js. Browser visual verification could
not be completed because this browser could not reach the local execution
environment. Docker is not installed in the preparation environment, so the
Docker image was not built there. Google OAuth and live YouTube upload were
not attempted without the user's channel. Complete the guide's demo and
private upload checks on your own computer.

No Google credentials, API keys, copyrighted BTS clips or BTS song recordings
are bundled. The demo uses original abstract art and a procedural tone loop.

Run the included tests after installing requirements-test.txt:

```bash
python -m unittest discover -s tests -v
```
