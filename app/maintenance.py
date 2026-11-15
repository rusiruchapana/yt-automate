from __future__ import annotations

import shutil
from datetime import timedelta

from .domain import stamp, utcnow


def cleanup_outputs(store, days):
    if days <= 0:
        return 0
    removed = 0
    with store.connect() as c:
        for row in c.execute("SELECT id,output FROM jobs WHERE youtube_id IS NOT NULL AND uploaded_at<? AND output IS NOT NULL",
                             (stamp(utcnow()-timedelta(days=days)),)).fetchall():
            path = (store.root / row["output"]).resolve()
            if path.is_relative_to(store.root / "outputs") and path.is_file():
                removed += path.stat().st_size
                path.unlink()
                c.execute("UPDATE jobs SET output=NULL WHERE id=?", (row["id"],))
    # Keep source files, credentials, scripts, SRT files and manifest records.
    return removed
