"""
=========================================================
Spotify OAuth Callback Server
=========================================================

Purpose:
- Open the Spotify authorization page in a browser
- Receive the OAuth authorization code from Spotify
- Display the authorization code for debugging or learning
- Used as a minimal OAuth demo or troubleshooting tool

Note:
- This script does NOT exchange the code for an access token.
- Token exchange is handled by Spotipy in the main server.
=========================================================
"""

# =========================================================
# IMPORTS
# =========================================================
from flask import Flask, request
import webbrowser

# =========================================================
# FLASK APP INITIALIZATION
# =========================================================
app = Flask(__name__)

# =========================================================
# SPOTIFY OAUTH CALLBACK ROUTE
# =========================================================
@app.route("/callback")
def callback():
    """
    Spotify redirects the user here after login approval.

    Example redirect URL:
    http://127.0.0.1:8888/callback?code=ABC123

    This function extracts the authorization code
    from the query string and displays it.
    """
    code = request.args.get("code")

    # Display authorization code in the browser
    return f"Spotify authorization code: {code}"

# =========================================================
# SPOTIFY AUTHORIZATION URL
# =========================================================
# IMPORTANT:
# Replace the placeholders below with values from
# your Spotify Developer Dashboard.
SPOTIFY_AUTH_URL = (
    "https://accounts.spotify.com/authorize?"
    "client_id=YOUR_CLIENT_ID"
    "&response_type=code"
    "&redirect_uri=YOUR_REDIRECT_URI"
    "&scope=SCOPES"
)

# =========================================================
# MAIN ENTRY POINT
# =========================================================
if __name__ == "__main__":
    print("Open your browser to authorize Spotify...")

    # Automatically opens the Spotify login page
    webbrowser.open(SPOTIFY_AUTH_URL)

    # Start Flask server to listen for Spotify redirect
    app.run(port=8888)
