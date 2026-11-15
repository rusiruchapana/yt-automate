#!/usr/bin/env python3
"""Render an original local demo without touching your studio database or Google."""
from pathlib import Path
import argparse
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.demo import seed
from app.domain import get_job
from app.render import render
from app.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="demo-preview.mp4")
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    if destination.exists():
        raise SystemExit("Choose a new output path; this command will not replace an existing file.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        store = Store(temporary)
        job_id = seed(store)
        result = store.root / render(store, get_job(store, job_id))
        shutil.copy2(result, destination)
    print("Demo preview created:", destination)
    print("Original abstract graphics and original tone loop. Preview only; no live upload occurred.")


if __name__ == "__main__":
    main()
