import os, time, json
from flask import Flask, redirect, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

app = Flask(__name__)

access_token = None
refresh_token = None
token_expires_at = 0  # unix time


# ---------- Helpers ----------

def get_basic_auth_header():
    import base64
    creds = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode("utf-8")
    b64 = base64.b64encode(creds).decode("utf-8")
    return {"Authorization": f"Basic {b64}"}


def refresh_access_token():
    global access_token, refresh_token, token_expires_at

    if refresh_token is None:
        return False

    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    headers = get_basic_auth_header()
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    r = requests.post(url, data=data, headers=headers)
    if r.status_code != 200:
        print("Refresh failed:", r.text)
        return False

    info = r.json()
    access_token = info["access_token"]
    # sometimes Spotify doesn’t return a new refresh_token; keep the old one
    token_expires_at = time.time() + info.get("expires_in", 3600) - 30
    print("Access token refreshed")
    return True


def ensure_token():
    """Refresh token if missing or expired."""
    global access_token
    if access_token is None or time.time() > token_expires_at:
        return refresh_access_token()
    return True


# ---------- Routes ----------

@app.route("/login")
def login():
    scope = (
        "user-read-playback-state "
        "user-modify-playback-state "
        "user-read-currently-playing "
        "user-read-playback-position"
    )

    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={SPOTIFY_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={SPOTIFY_REDIRECT_URI}"
        f"&scope={scope.replace(' ', '%20')}"
    )
    return redirect(auth_url)


@app.route("/callback")
def callback():
    global access_token, refresh_token, token_expires_at

    code = request.args.get("code")
    if not code:
        return "No code provided", 400

    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
    }
    headers = get_basic_auth_header()
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    r = requests.post(url, data=data, headers=headers)
    if r.status_code != 200:
        return f"Token request failed: {r.text}", 400

    info = r.json()
    access_token = info["access_token"]
    refresh_token = info.get("refresh_token", refresh_token)
    token_expires_at = time.time() + info.get("expires_in", 3600) - 30

    return "<h1>Spotify linked! You can close this tab.</h1>"


@app.route("/current")
def current():
    """Endpoint that Arduino will poll."""
    if not ensure_token():
        return jsonify({"error": "not_authenticated"}), 401

    headers = {"Authorization": f"Bearer {access_token}"}

    # 1) what’s currently playing
    rp = requests.get("https://api.spotify.com/v1/me/player/currently-playing",
                      headers=headers)
    if rp.status_code != 200:
        return jsonify({"error": "no_playback"}), rp.status_code

    data = rp.json()
    if not data or "item" not in data:
        return jsonify({"error": "no_track"}), 200

    item = data["item"]
    is_playing = data.get("is_playing", False)
    song = item.get("name", "")
    artist = ", ".join(a["name"] for a in item["artists"])
    duration_ms = item.get("duration_ms", 0)
    progress_ms = data.get("progress_ms", 0)
    track_id = item.get("id")

    # 2) audio features (tempo, energy)
    tempo = None
    energy = None
    if track_id:
        af = requests.get(
            f"https://api.spotify.com/v1/audio-features/{track_id}",
            headers=headers,
        )
        if af.status_code == 200:
            feat = af.json()
            tempo = feat.get("tempo")
            energy = feat.get("energy")

    return jsonify(
        {
            "is_playing": is_playing,
            "song": song,
            "artist": artist,
            "progress_ms": progress_ms,
            "duration_ms": duration_ms,
            "tempo": tempo,
            "energy": energy,
        }
    )


if __name__ == "__main__":
    # Run on all interfaces so Arduino on same Wi-Fi can reach it
    app.run(host="0.0.0.0", port=5000)
