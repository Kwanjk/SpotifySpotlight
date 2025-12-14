"""
=========================================================
Spotify IoT Flask Server
=========================================================

Purpose:
- Authenticate with Spotify using OAuth
- Control playback (play, pause, next, previous, volume)
- Fetch currently playing track + metadata
- Map music characteristics (genre, BPM, popularity, explicit)
  into RGB color values
- Serve JSON responses to an Arduino / IoT device

=========================================================
"""

# =========================================================
# IMPORTS
# =========================================================
import time
import colorsys
from flask import Flask, request, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# =========================================================
# FLASK APP INITIALIZATION
# =========================================================
app = Flask(__name__)

# =========================================================
# SPOTIFY CONFIGURATION
# =========================================================
# These values come from the Spotify Developer Dashboard
SPOTIPY_CLIENT_ID = "bb2b02914d244902a92302523becf00a"
SPOTIPY_CLIENT_SECRET = "4429cdecaec14985a3cb75c1ec6cbc02"

# IMPORTANT:
# This MUST match the redirect URI configured in Spotify
SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

# Permissions requested from Spotify
SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing"
)

# =========================================================
# SPOTIFY AUTHENTICATION
# =========================================================
# Handles OAuth flow automatically and caches token locally
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=".cache-spotify-iot"  # avoids re-login
    )
)

# =========================================================
# HELPER FUNCTIONS (COLOR MATH)
# =========================================================
def clamp(x, lo=0, hi=255):
    """Clamp integer to valid RGB range."""
    return max(lo, min(hi, int(x)))

def clamp01(x):
    """Clamp float between 0.0 and 1.0."""
    return max(0.0, min(1.0, float(x)))

def hue_to_rgb(h, s=1.0, v=1.0):
    """
    Convert HSV color values to RGB.
    Hue is in range [0,1].
    """
    r, g, b = colorsys.hsv_to_rgb(clamp01(h), clamp01(s), clamp01(v))
    return int(r * 255), int(g * 255), int(b * 255)

def mix_rgb(colors_with_weights):
    """
    Mix multiple RGB colors using weighted averages.
    """
    total = sum(w for _, w in colors_with_weights) or 1.0
    r = sum(c[0] * w for c, w in colors_with_weights) / total
    g = sum(c[1] * w for c, w in colors_with_weights) / total
    b = sum(c[2] * w for c, w in colors_with_weights) / total
    return clamp(r), clamp(g), clamp(b)

# =========================================================
# GENRE → COLOR BUCKETS
# =========================================================
# Each bucket represents a base hue on the color wheel
BUCKETS = [
    ("RED",    0.00),
    ("ORANGE", 0.08),
    ("YELLOW", 0.14),
    ("GREEN",  0.33),
    ("CYAN",   0.50),
    ("BLUE",   0.62),
    ("PURPLE", 0.78),
    ("PINK",   0.90),
]

# Keywords used to associate Spotify genres with buckets
GENRE_KEYWORDS = {
    "RED": ["rock", "metal", "punk", "emo"],
    "ORANGE": ["latin", "reggaeton", "afrobeats"],
    "YELLOW": ["pop", "k-pop", "j-pop"],
    "GREEN": ["indie", "folk", "country", "bluegrass"],
    "CYAN": ["edm", "house", "trance"],
    "BLUE": ["ambient", "chill", "lofi"],
    "PURPLE": ["hip hop", "rap", "r&b"],
    "PINK": ["jazz", "classical", "instrumental"],
}

def score_buckets(genres):
    """
    Assign weights to color buckets based on genre keywords.
    """
    text = " ".join(genres).lower()
    weights = {name: 0.0 for name, _ in BUCKETS}

    for bucket, keywords in GENRE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                weights[bucket] += 1.0

    # Fallback if no genres detected
    if sum(weights.values()) == 0:
        weights["CYAN"] = 1.0
        weights["GREEN"] = 0.7
        weights["BLUE"] = 0.5

    # Normalize weights
    total = sum(weights.values()) or 1.0
    for k in weights:
        weights[k] /= total

    return weights

def bucket_base_rgb(weights, temp_c, popularity, explicit):
    """
    Convert weighted genre buckets into a final RGB color.
    Temperature and popularity slightly influence brightness/saturation.
    """
    pop = clamp01((popularity or 50) / 100)

    saturation = clamp01(0.6 + 0.3 * pop + (0.1 if explicit else 0.0))
    brightness = clamp01(0.5 + 0.4 * pop)

    colors = []
    for name, base_hue in BUCKETS:
        w = weights.get(name, 0)
        if w > 0:
            colors.append((hue_to_rgb(base_hue, saturation, brightness), w))

    return mix_rgb(colors)

# =========================================================
# SPOTIFY DATA FETCHING
# =========================================================
_artist_genre_cache = {}

def safe_get_current_genres():
    """
    Safely fetch current track metadata.
    Returns:
    (track_name, artist_name, genres, popularity, explicit, track_id)
    """
    current = sp.current_playback()
    if not current or not current.get("item"):
        return "No Song", "Unknown", [], 50, False, None

    item = current["item"]
    track_id = item.get("id")

    artist = item["artists"][0]
    artist_id = artist.get("id")

    if artist_id in _artist_genre_cache:
        genres = _artist_genre_cache[artist_id]
    else:
        genres = sp.artist(artist_id).get("genres", [])
        _artist_genre_cache[artist_id] = genres

    return (
        item.get("name"),
        artist.get("name"),
        genres,
        item.get("popularity", 50),
        bool(item.get("explicit", False)),
        track_id
    )

# =========================================================
# BPM COLOR MODE
# =========================================================
def bpm_to_rgb(tempo, energy):
    """
    Convert BPM + energy to RGB color.
    Faster tempo → warmer color.
    """
    tempo = max(60, min(180, tempo))
    p = (tempo - 60) / 120
    return clamp(255 * p), clamp(255 * energy), clamp(255 * (1 - p))

# =========================================================
# FLASK ROUTES
# =========================================================
@app.route("/")
def home():
    """Server health check."""
    return "Spotify IoT Server is Running!"

@app.route("/playpause")
def play_pause():
    """Toggle play/pause."""
    current = sp.current_playback()
    if current and current.get("is_playing"):
        sp.pause_playback()
        return jsonify(action="paused")
    else:
        sp.start_playback()
        return jsonify(action="playing")

@app.route("/next")
def next_track():
    """Skip to next track."""
    sp.next_track()
    return jsonify(action="next")

@app.route("/previous")
def previous_track():
    """Go to previous track."""
    sp.previous_track()
    return jsonify(action="previous")

@app.route("/volume")
def volume():
    """
    Adjust volume.
    Use ?set=XX or ?delta=±X
    """
    current = sp.current_playback()
    if not current or not current.get("device"):
        return jsonify(error="No active device"), 400

    cur_vol = current["device"]["volume_percent"]
    set_v = request.args.get("set", type=int)
    delta = request.args.get("delta", type=int)

    if set_v is not None:
        new_vol = clamp(set_v, 0, 100)
    elif delta is not None:
        new_vol = clamp(cur_vol + delta, 0, 100)
    else:
        return jsonify(error="Missing parameters"), 400

    sp.volume(new_vol)
    return jsonify(volume=new_vol)

@app.route("/update_context")
def update_context():
    """
    Main endpoint for Arduino / IoT device.
    Returns song metadata and RGB values.
    """
    temp = request.args.get("temp", type=float)
    mode = (request.args.get("mode") or "TEMP").upper()

    track, artist, genres, popularity, explicit, track_id = safe_get_current_genres()

    weights = score_buckets(genres)
    r, g, b = bucket_base_rgb(weights, temp, popularity, explicit)

    return jsonify(
        song=track[:15],
        artist=artist[:15],
        r=r,
        g=g,
        b=b,
        genres=genres[:3],
        popularity=popularity,
        explicit=explicit
    )

# =========================================================
# MAIN ENTRY POINT
# =========================================================
if __name__ == "__main__":
    print("Authenticating with Spotify...")
    sp.current_user()  # Forces OAuth login
    print("Spotify authentication successful.")

    print("Starting Flask server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
