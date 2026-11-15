#!/usr/bin/env python3
"""One-time Desktop OAuth connection. Run locally; never paste a password/token into chat."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.store import Store
from app.youtube import SCOPES, TOKEN_URL, Transport, atomic_json, decode, get_channel


def main():
    parser = argparse.ArgumentParser(description="Connect the local studio to your YouTube channel.")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--channel-id", default="")
    args = parser.parse_args()
    root = Path(os.environ.get("STUDIO_DATA", Path(__file__).resolve().parents[1] / "data"))
    store = Store(root)
    config_path = root / "secrets" / "client_secrets.json"
    if not config_path.exists():
        raise SystemExit("Save a Google OAuth Desktop app JSON file as data/secrets/client_secrets.json first. See GUIDE.md.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if "installed" not in config:
        raise SystemExit("Use an OAuth client of type Desktop app, not Web application or service account.")
    client = config["installed"]
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    redirect = "http://localhost:8765/"
    received = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.headers.get("Host") not in {"localhost:8765", "127.0.0.1:8765"}:
                self.send_error(400)
                return
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/":
                self.send_error(404)
                return
            query = urllib.parse.parse_qs(parsed.query)
            if not hmac.compare_digest(query.get("state", [""])[0], state):
                self.send_error(400, "Authorization state did not match.")
                return
            if query.get("error"):
                received["error"] = "Google authorization was not granted."
            elif query.get("code"):
                received["code"] = query["code"][0]
            else:
                self.send_error(400)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"<h1>Return to your terminal</h1><p>The studio is finishing the channel connection. You can close this tab.</p>")

    server = HTTPServer((os.environ.get("OAUTH_BIND_ADDRESS", "127.0.0.1"), 8765), Callback)
    server.timeout = 1
    params = {"client_id": client["client_id"], "redirect_uri": redirect, "response_type": "code",
              "scope": " ".join(SCOPES), "state": state, "access_type": "offline", "prompt": "consent",
              "code_challenge": challenge, "code_challenge_method": "S256"}
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    print("Open this Google authorization URL on THIS computer. Choose your intended channel:", flush=True)
    print(url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    deadline = time.time() + 600
    try:
        while not received and time.time() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if received.get("error") or not received.get("code"):
        raise SystemExit(received.get("error", "Authorization timed out. Run the helper again."))
    transport = Transport()
    form = {"grant_type": "authorization_code", "code": received["code"], "code_verifier": verifier,
            "redirect_uri": redirect, "client_id": client["client_id"], "client_secret": client["client_secret"]}
    r = transport.request("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, urllib.parse.urlencode(form).encode())
    if r.status != 200:
        raise SystemExit("Google could not exchange the authorization code. Check the Desktop client and run again.")
    result = decode(r)
    if not result.get("refresh_token"):
        raise SystemExit("No refresh token was returned. Revoke the old grant in your Google account, then reconnect with consent.")
    token = {"client_id": client["client_id"], "client_secret": client["client_secret"],
             "access_token": result["access_token"], "refresh_token": result["refresh_token"],
             "expires_at": time.time()+int(result.get("expires_in", 3600))}
    channels = get_channel(token, transport)
    if args.channel_id:
        channels = [c for c in channels if c["id"] == args.channel_id]
    if len(channels) != 1:
        print("A single channel could not be selected. Authorized channel IDs:")
        for channel in channels:
            print(channel["id"], channel["snippet"]["title"])
        raise SystemExit("Run again with --channel-id YOUR_CHANNEL_ID, or create/select the correct channel in Google.")
    token["channel_id"] = channels[0]["id"]
    token["channel_title"] = channels[0]["snippet"]["title"]
    atomic_json(root / "secrets" / "youtube-token.json", token)
    # Connecting never enables publishing by itself.
    store.set_settings({"uploads_enabled": False})
    print("Connected:", token["channel_title"], "(" + token["channel_id"] + ")")
    print("Uploads remain OFF. Return to the dashboard and verify the channel name before enabling them.")


if __name__ == "__main__":
    main()
