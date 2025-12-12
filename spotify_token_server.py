import time
from flask import Flask, request, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth

app = Flask(__name__)

# --- CONFIGURATION ---
SPOTIPY_CLIENT_ID = 'bb2b02914d244902a92302523becf00a'
SPOTIPY_CLIENT_SECRET = '4429cdecaec14985a3cb75c1ec6cbc02'

# IMPORTANT: redirect to YOUR PC (local) — NOT the Arduino
SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "user-modify-playback-state user-read-playback-state"

# Optional: store token cache in a file with a custom name
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=".cache-spotify-iot",  # so you don't have to log in every run
    )
)
print(sp.albums)


@app.route('/')
def home():
    return "Spotify IoT Server is Running!"

# --- ARDUINO ENDPOINTS ---

@app.route('/next')
def next_track():
    try:
        sp.next_track()
        return jsonify({"status": "success", "action": "next"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/previous')
def previous_track():
    try:
        sp.previous_track()
        return jsonify({"status": "success", "action": "previous"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/playpause')
def play_pause():
    try:
        current = sp.current_playback()
        if current and current.get('is_playing'):
            sp.pause_playback()
            action = "paused"
        else:
            sp.start_playback()
            action = "playing"
        return jsonify({"status": "success", "action": action})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/update_context')
def update_context():
    # 1. Get Temp from Arduino Request
    temp = request.args.get('temp', type=float)

    # 2. Get Current Song Info from Spotify
    track_name = "No Song"
    artist_name = "Unknown"
    energy = 0.5  # Default medium energy

    try:
        current = sp.current_playback()
        if current and current.get('item'):
            track_name = current['item']['name']
            artist_name = current['item']['artists'][0]['name']
            track_id = current['item']['id']

            features_list = sp.audio_features([track_id])
            if features_list and features_list[0]:
                features = features_list[0]
                energy = features.get('energy', 0.5)
    except Exception as e:
        print(f"Spotify Error: {e}")

    # 3. Determine Color Logic
    r, g, b = 0, 0, 0

    if temp is not None and temp > 25:
        # Hot: Red/Orange base
        r = 255
        g = int(100 * energy)  # More energy = more yellow
    else:
        # Cold: Blue/Teal base
        b = 255
        g = int(100 * energy)

    return jsonify({
        "song": track_name[:15],
        "artist": artist_name[:15],
        "r": r, "g": g, "b": b
    })

if __name__ == '__main__':

    

    # 1️⃣ Force Spotify login once at startup
    print("If a browser opens, log into Spotify and approve the app...")
    _ = sp.current_user()   # This triggers OAuth and caches the token
    print("Spotify login success. Token cached.", _)

    # 2️⃣ Now start the Flask server for your Arduino
    # Replace 192.168.1.161 with your actual PC LAN IP if you want to see it clearly
    print("Starting Flask server on http://0.0.0.0:5000")
    print("From Arduino, call: http://<YOUR_PC_IP>:5000/update_context?temp=25.0")
    app.run(host='0.0.0.0', port=5000)

