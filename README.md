# 🎵 Spotify Spotlight

> MKR IoT Carrier + Flask + Spotify Web API

---

## 📖 Overview

**Spotify Spotlight** connects a Spotify account to an **Arduino MKR IoT Carrier** using a Python Flask backend as a bridge.

The system:

* Authenticates with Spotify using OAuth
* Retrieves live playback information (song, artist, play/pause state)
* Maps music characteristics (genre, popularity, explicit flag, tempo) into RGB LED colors
* Displays a smooth, scrolling “Now Playing” UI on the IoT Carrier
* Allows playback control via both **capacitive touch buttons** and **Arduino IoT Cloud**

---

## 🏗️ System Architecture

### 🎵 Spotify Web API

* Provides current playback state and metadata
* Uses OAuth 2.0 Authorization Code Flow
* Requires a **Spotify Premium account** for playback control

---

### 💻 Python Flask Backend (Laptop)

The Flask server acts as the **central logic engine**.

#### Authentication

* Opens a local browser for Spotify login
* Uses redirect URI:

  ```
  http://127.0.0.1:8888/callback
  ```
* Access tokens are cached locally using Spotipy

#### Responsibilities

* Receives temperature + humidity from Arduino
* Fetches current Spotify playback state
* Maps music context → RGB color values
* Exposes REST endpoints for Arduino control

#### API Endpoints

| Endpoint          | Description                                                 |
| ----------------- | ----------------------------------------------------------- |
| `/update_context` | Returns JSON with song info, playback state, and RGB values |
| `/playpause`      | Toggle play / pause                                         |
| `/next`           | Skip to next track                                          |
| `/previous`       | Go to previous track                                        |
| `/volume?set=XX`  | Set volume (0–100)                                          |

---

### 🤖 Arduino MKR IoT Carrier

* **Network:** Connects to the same Wi-Fi network as the laptop
* **Inputs:**

  * Capacitive touch buttons
  * Arduino IoT Cloud switches
* **Sensors:** Reads ambient temperature and humidity
* **Outputs:**

  * RGB LEDs (solid color or animated patterns)
  * TFT display with smooth scrolling song + artist text
  * Play / pause status icon

---

## ✅ Prerequisites

* 🎧 Spotify **Premium** account
* 🔑 Spotify Developer account + registered app
* 🐍 Python 3.9+
* 🔌 Arduino MKR WiFi 1010
* 📟 MKR IoT Carrier
* 📡 Shared Wi-Fi network or personal hotspot (recommended)

---

## 🚀 Setup Instructions

### 1️⃣ Spotify Developer Configuration

1. Create an app in the
   [https://developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Copy:

   * Client ID
   * Client Secret
3. Add this **Redirect URI**:

   ```
   http://127.0.0.1:8888/callback
   ```

---

### 2️⃣ Python Flask Backend

#### Create `.env`

```env
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

#### Install Dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt`

```txt
flask
spotipy
python-dotenv
requests
```

#### Run Server

```bash
python spotify_token_server.py
```

* A browser will open for Spotify login
* Server listens on:

  ```
  http://0.0.0.0:5000
  ```
* Note your laptop’s **LAN IP** (e.g. `192.168.1.157`)

---

### 3️⃣ Arduino Configuration

#### Wi-Fi Credentials

Create `arduino_secrets.h`:

```cpp
#define SECRET_SSID  "your_wifi_ssid"
#define SECRET_PASS  "your_wifi_password"
```

#### Update Server IP

In the Arduino sketch:

```cpp
IPAddress serverIP(192, 168, 1, 157); // CHANGE TO YOUR LAPTOP IP
```

#### Upload Sketch

* Board: **Arduino MKR WiFi 1010**
* Upload the provided sketch

---

## 🎮 Running the System

1. Start the Flask server
2. Open Spotify on any device and start playback
3. Power on the MKR IoT Carrier
4. Arduino polls the server every ~10 seconds

### Touch Controls

| Touch Button | Action         |
| ------------ | -------------- |
| TOUCH0       | Previous Track |
| TOUCH2       | Play / Pause   |
| TOUCH4       | Next Track     |

---

## 🖥️ Display Features

* Smooth horizontal scrolling for long song titles
* Play / pause icon synced with Spotify playback
* Minimal redraw strategy (no flicker or ghosting)
* Color-coded song mood display

---

## 💡 LED Behavior

* **TEMP Mode:** Color influenced by temperature + genre
* **PATTERN Mode:** Pulse / Blink animations
* **BPM Mode:** Color derived from tempo and energy
* **Cloud Color Override:** Manual color selection via IoT Cloud

---

## 🔧 Troubleshooting

### Arduino Can’t Connect to Server

* Ensure **same Wi-Fi network**
* Confirm IP address matches laptop
* Check firewall allows port **5000**

### Spotify OAuth Errors

* Redirect URI must match **exactly**
* `.env` file must match Spotify dashboard
* Restart Flask server after changes

---

## 🧠 Notes

* Spotify playback control requires an **active device**
* If playback commands fail, open Spotify manually once
* OAuth tokens are cached to avoid repeated logins

---

## 📄 License

Open source for educational use.

---

## 👥 Contributors

- **Joshua Kwam**
- **Joseph Cin**
- **Benjamin Donkor**
- **Cadell Otoo**
- **Oluwaemi Abiodun**

INST347 — Group Project
Arduino + Flask + Spotify Integration