#!/usr/bin/env python3
"""Consistent SQLite snapshot plus source media, manifests and local credentials."""
from __future__ import annotations

import argparse
import contextlib
import os
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--without-videos", action="store_true", help="Omit MP4 cache to make a smaller backup; interrupted uploads then need manual reconciliation")
    args = parser.parse_args()
    root = Path(os.environ.get("STUDIO_DATA", Path(__file__).resolve().parents[1]/"data"))
    store = Store(root)
    folder = root / "backups"
    folder.mkdir(exist_ok=True)
    target = folder / ("purple-backup-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + ".zip")
    with tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / "studio.sqlite3"
        with contextlib.closing(sqlite3.connect(snapshot)) as dest, store.connect() as source:
            source.backup(dest)
            # The archive needs a standalone DB, not changes left in a WAL sidecar.
            dest.execute("PRAGMA journal_mode=DELETE")
            # Without the MP4 cache, ready and interrupted jobs need to be rendered/reviewed again.
            dest.execute("UPDATE settings SET value='false' WHERE key='uploads_enabled'")
            if args.without_videos:
                dest.execute("UPDATE jobs SET status='queued',preapproved=0,error='Re-rendering from a backup without MP4 cache; review again.' WHERE youtube_id IS NULL AND upload_session IS NULL AND status!='cancelled'")
                dest.execute("UPDATE jobs SET status='upload_unknown',error='MP4 cache omitted. Check Studio and link an existing video; do not start a fresh upload automatically.' WHERE youtube_id IS NULL AND upload_session IS NOT NULL")
                dest.execute("UPDATE jobs SET output=NULL")
            dest.commit()
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.write(snapshot, "studio.sqlite3")
            for name in ("assets", "secrets", "outputs"):
                for path in (root / name).rglob("*"):
                    if not path.is_file() or (args.without_videos and path.suffix.lower()==".mp4"):
                        continue
                    z.write(path, path.relative_to(root))
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    print("Backup created:", target)
    print("This archive includes local OAuth credentials. Keep it private and store a copy on a protected drive.")


if __name__ == "__main__":
    main()
