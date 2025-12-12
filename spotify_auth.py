from flask import Flask, request
import webbrowser

app = Flask(__name__)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    return f"Spotify authorization code: {code}"

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=YOUR_REDIRECT_URI&scope=SCOPES"


if __name__ == "__main__":
    print("Open your browser to authorize Spotify...")
    webbrowser.open(SPOTIFY_AUTH_URL)  # Replace with the auth URL from Spotify dashboard
    app.run(port=8888)

