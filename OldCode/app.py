"""
Spotify IoT Controller Server
-----------------------------
This Flask server allows an external device (e.g., Arduino IoT setup)
to control Spotify playback and receive contextual track/audio data.

Key Features:
 - OAuth login against your personal Spotify account
 - Playback control endpoints (next, previous, pause/play)
 - Context endpoint (/update_context) returns current track data + RGB
 - Token cached locally (no repeated logins)
 - Reads secrets safely from .env

PREREQUISITES:
 1. Register a Spotify App at:
    https://developer.spotify.com/dashboard

 2. Add redirect URI in the Spotify developer portal:
    http://127.0.0.1:8888/callback

 3. Create `.env` file in SAME directory (see template below)

 4. Install dependencies:
    pip install -r requirements.txt

 5. FIRST RUN:
    - Flask will auto-trigger Spotify login
    - Grant permissions ONCE
    - Token cached for future use
"""

import time
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# ----------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# ----------------------------------------------------
load_dotenv()  # reads .env file automatically

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET or not SPOTIPY_REDIRECT_URI:
    raise ValueError(
        "\n❌ Missing environment variables.\n"
        "Make sure your .env file contains:\n"
        "SPOTIPY_CLIENT_ID=\nSPOTIPY_CLIENT_SECRET=\nSPOTIPY_REDIRECT_URI=\n"
    )

# Spotify playback & track permissions
SCOPE = "user-modify-playback-state user-read-playback-state"

# ----------------------------------------------------
# INITIALIZE SPOTIFY API CLIENT
# Token stored locally so login NOT needed every run
# ----------------------------------------------------
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=".cache-spotify-iot",
    )
)

# ----------------------------------------------------
# FLASK APP SETUP
# ----------------------------------------------------
app = Flask(__name__)


@app.route("/")
def home():
    """Basic status endpoint."""
    return "Spotify IoT Server is Running!"


# ----------------------------------------------------
# SPOTIFY COMMAND ENDPOINTS FOR ARDUINO
# ----------------------------------------------------
@app.route("/next")
def next_track():
    """Skip to next Spotify track."""
    try:
        sp.next_track()
        return jsonify({"status": "success", "action": "next"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/previous")
def previous_track():
    """Return to previous Spotify track."""
    try:
        sp.previous_track()
        return jsonify({"status": "success", "action": "previous"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/playpause")
def play_pause():
    """
    Toggle play/pause:
        - If music currently playing → pause
        - If paused → resume
    """
    try:
        current = sp.current_playback()

        # When active & playing → pause it
        if current and current.get("is_playing"):
            sp.pause_playback()
            action = "paused"
        else:
            sp.start_playback()
            action = "playing"

        return jsonify({"status": "success", "action": action})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ----------------------------------------------------
# CONTEXTUAL COLOR ENDPOINT
# Arduino calls:
#   GET /update_context?temp=26.5
#
# Returns:
#  {
#    "song": "Track Name",
#    "artist": "Artist",
#    "r": ..., "g": ..., "b": ...
#  }
# ----------------------------------------------------
@app.route("/update_context")
def update_context():
    """
    Returns:
      - Current song name + artist
      - RGB values influenced by:
          * Temperature data from Arduino
          * Track energy (Spotify Audio Features)
    """
    temp = request.args.get("temp", type=float)

    track_name = "No Song"
    artist_name = "Unknown"
    energy = 0.5  # safe fallback

    try:
        current = sp.current_playback()

        # If something is currently playing
        if current and current.get("item"):
            track_name = current["item"]["name"]
            artist_name = current["item"]["artists"][0]["name"]
            track_id = current["item"]["id"]

            # Get Spotify Audio Features (energy, danceability, etc)
            track_features = sp.audio_features([track_id])

            if track_features and track_features[0]:
                energy = track_features[0].get("energy", 0.5)

    except Exception as e:
        print(f"Spotify Error: {e}")

    # Determine LED Colors
    # Hot → RED/ORANGE
    # Cold → BLUE/TEAL
    r, g, b = 0, 0, 0

    if temp is not None and temp > 25:
        r = 255
        g = int(100 * energy)
    else:
        b = 255
        g = int(100 * energy)

    return jsonify(
        {
            "song": track_name[:15],
            "artist": artist_name[:15],
            "r": r,
            "g": g,
            "b": b,
        }
    )


# ----------------------------------------------------
# APP ENTRY POINT
# ----------------------------------------------------
if __name__ == "__main__":

    print("🔐 Launching Spotify OAuth (only needed first run)...")
    _ = sp.current_user()  # triggers Spotify login popup
    print("✔️ Spotify login successful (token cached).")

    print("\n🚀 Flask Server Running:")
    print("   → http://0.0.0.0:5000")
    print("\n📌 Arduino endpoint example:")
    print("   http://<YOUR_PC_IP>:5000/update_context?temp=25.0\n")

    app.run(host="0.0.0.0", port=5000)
