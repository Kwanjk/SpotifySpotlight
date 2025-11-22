# Spotify Spotlight – MKR IoT Carrier + Flask + Spotify API

This project connects a Spotify account to an Arduino MKR IoT Carrier.  
A Python Flask backend talks to the Spotify Web API and exposes a simple `/current` endpoint that the Arduino polls over Wi-Fi. The MKR IoT Carrier display shows the current song, artist, and room temperature, while the onboard RGB LEDs pulse based on the track’s energy and change color with temperature.

## Architecture Overview

- **Spotify Web API**
  - Provides user playback information and audio features (tempo, energy, etc.).
  - Uses the OAuth 2.0 authorization code flow.

- **Python Flask Backend (Laptop)**
  - Handles Spotify login (`/login`) and token exchange (`/callback`).
  - Periodically refreshes the access token using a refresh token.
  - Exposes `/current`, which returns a compact JSON object for the Arduino:
    ```json
    {
      "is_playing": true,
      "song": "Song Title",
      "artist": "Artist Name",
      "progress_ms": 12345,
      "duration_ms": 200000,
      "tempo": 120.5,
      "energy": 0.75
    }
    ```

- **Arduino MKR IoT Carrier**
  - Connects to the same Wi-Fi network as the laptop (typically a phone hotspot).
  - Sends `GET /current` requests to the Flask server every 2 seconds.
  - Uses the JSON response to:
    - Display the song and artist on the round LCD.
    - Read ambient temperature from the onboard sensor.
    - Pulse the LED brightness using a sine wave scaled by track energy.
    - Map temperature to color (blue for cooler, red for warmer).

## Prerequisites

- Spotify Premium account (recommended for consistent playback behavior)
- Spotify Developer account and app
- Python 3 + `pip`
- Arduino MKR WiFi 1010 + MKR IoT Carrier
- USB cable and Arduino IDE or Arduino IoT Cloud
- A personal Wi-Fi hotspot or home network

## Setup

### 1. Spotify Developer Configuration

1. Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Copy the **Client ID** and **Client Secret**.
3. Add a Redirect URI, for example:
   ```text
   http://10.172.40.158:5000/callback
   ```

### 2. Python Backend

1. Clone or download this repository.
2. In the project folder, create a `.env` file:
   ```
   SPOTIFY_CLIENT_ID=your_client_id_here
   SPOTIFY_CLIENT_SECRET=your_client_secret_here
   SPOTIFY_REDIRECT_URI=http://10.172.40.158:5000/callback
   ```
3. Install dependencies:
   ```bash
   pip install flask requests python-dotenv
   ```
4. Run the server:
   ```bash
   python3 app.py
   ```
5. In your browser, go to:
   ```
   http://10.172.40.158:5000/login
   ```
6. Log in and authorize the app. You should see a confirmation message.

### 3. Arduino Configuration

1. Turn on a phone hotspot and connect your laptop to it.
2. In `arduino_secrets.h` (or the Arduino IoT Cloud secrets panel), set:
   ```cpp
   #define SECRET_SSID  "your-hotspot-ssid"
   #define SECRET_PASS  "your-hotspot-password"
   ```
3. In the Arduino sketch, set the server IP/port to match your laptop:
   ```cpp
   IPAddress serverIP(10, 172, 40, 158);
   int serverPort = 5000;
   ```
4. Upload the sketch to the MKR WiFi 1010 and open the Serial Monitor at 9600 baud.

## Running the System

1. Start the Flask server (`python3 app.py`).
2. Make sure Spotify is playing a track on your account.
3. Power/reset the Arduino.
4. Watch the Serial Monitor for HTTP status codes and JSON.

The MKR IoT Carrier should:
- Show the current song and artist
- Display the ambient temperature
- Pulse LEDs according to energy and color-shift based on temperature

## Troubleshooting

### Stuck on "Waiting for Spotify data"
- Check that the Flask server is running and reachable at `http://<laptop-ip>:5000/current`
- Confirm that the Arduino and laptop are on the same Wi-Fi network
- Make sure you visited `/login` and authorized Spotify

### 401 / not_authenticated
- Redo the `/login` step to refresh tokens

### Status 0 or 500 in Serial Monitor
- Network issue or wrong `serverIP` / `serverPort`
- Verify hotspot SSID/password and laptop IP

## Future Improvements

- Add buttons to skip/play/pause from the Arduino
- Use SSL/TLS on the backend and eventually migrate to HTTPS on the device
- Persist tokens to disk so the server can restart without re-authenticating


---

## 4. Demo Plan / Script (3–5 minutes)

You can more or less say this:

1. **Intro (20–30 seconds)**  
   - “Our project is called *Spotify Spotlight*. It connects a Spotify account to an Arduino MKR IoT Carrier and visualizes the current track and environment using the display and LEDs.”

2. **Architecture (45–60 seconds)**  
   - Briefly point at a diagram or slide with three boxes (Spotify, Flask server, Arduino).
   - Explain: “Spotify → Flask → Arduino” in one or two sentences each.

3. **Live Run (2–3 minutes)**  
   - Show the Flask terminal already running.  
   - In a browser, quickly show `/login` (or say ‘I’ve already logged in via Spotify’).  
   - Start playing a recognizable song on Spotify.  
   - Hold up the Arduino:  
     - “The device polls the `/current` endpoint every two seconds.”  
     - “You can see the song title and artist here.”  
     - “The temperature sensor reads the room temperature and maps it to an LED color—cool is blue, warm is red.”  
     - “The brightness of the LEDs pulses with a sine function scaled by the track’s energy value from Spotify.”

4. **Closing (30–45 seconds)**  
   - Mention one challenge (UMD-IOT blocking device-to-device traffic → solved via hotspot).  
   - Mention one potential extension (control playback from the Arduino, visualize tempo as strobe, etc.).  
   - “Overall, this project demonstrates integrating a web API, a Python backend, and an embedded IoT device into one interactive system.”

---

## 5. Arduino Sketch 

```cpp
#include <WiFiNINA.h>
#include <ArduinoHttpClient.h>
#include <ArduinoJson.h>
#include <Arduino_MKRIoTCarrier.h>
#include "arduino_secrets.h"

MKRIoTCarrier carrier;

char ssid[] = SECRET_SSID;
char pass[] = SECRET_PASS;

// laptop IP + Flask port
IPAddress serverIP(10, 172, 40, 158);
int serverPort = 5000;

WiFiClient wifiClient;
HttpClient http(wifiClient, serverIP, serverPort);

unsigned long lastPoll = 0;
const unsigned long POLL_INTERVAL = 2000;

void connectWiFi() {
  while (WiFi.begin(ssid, pass) != WL_CONNECTED) {
    Serial.println("Connecting to WiFi...");
    delay(1000);
  }
  Serial.print("Connected. IP: ");
  Serial.println(WiFi.localIP());
}

void showWaitingScreen(const char* msg) {
  carrier.display.fillScreen(ST77XX_BLACK);
  carrier.display.setTextSize(2);
  carrier.display.setTextColor(ST77XX_WHITE);
  carrier.display.setCursor(10, 100);
  carrier.display.println("Waiting for");
  carrier.display.setCursor(10, 120);
  carrier.display.println(msg);
}

void setup() {
  Serial.begin(9600);
  delay(1500);

  CARRIER_CASE = true;
  carrier.begin();
  carrier.display.setRotation(0);

  connectWiFi();
  showWaitingScreen("Spotify data");
}

void loop() {
  if (millis() - lastPoll < POLL_INTERVAL) return;
  lastPoll = millis();

  // 1) GET /current from Flask
  http.beginRequest();
  http.get("/current");
  http.endRequest();

  int statusCode = http.responseStatusCode();
  String body = http.responseBody();

  Serial.print("Status: "); Serial.println(statusCode);
  Serial.println(body);

  if (statusCode != 200) {
    showWaitingScreen("backend (err)");
    return;
  }

  // 2) Parse JSON
  DynamicJsonDocument doc(1024);
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    Serial.println("JSON error");
    showWaitingScreen("JSON error");
    return;
  }

  if (doc.containsKey("error")) {
    Serial.println("Backend error or no track");
    showWaitingScreen("Spotify track");
    return;
  }

  bool isPlaying = doc["is_playing"];
  const char* song = doc["song"] | "";
  const char* artist = doc["artist"] | "";
  float tempo = doc["tempo"] | 120.0;
  float energy = doc["energy"] | 0.5;

  float tempC = carrier.Env.readTemperature();

  // 3) Update display
  carrier.display.fillScreen(ST77XX_BLACK);
  carrier.display.setTextSize(1);
  carrier.display.setCursor(5, 60);
  carrier.display.print("Song: ");
  carrier.display.println(song);
  carrier.display.setCursor(5, 80);
  carrier.display.print("Artist: ");
  carrier.display.println(artist);
  carrier.display.setCursor(5, 110);
  carrier.display.print("Temp: ");
  carrier.display.print(tempC);
  carrier.display.println(" C");

  // 4) LED pulse using energy and tempo
  float speed = 0.002 + energy * 0.006;
  float beat = sin(millis() * speed) * 0.5 + 0.5;
  int brightness = (int)(beat * 255);

  float t = constrain((tempC - 15.0) / 15.0, 0.0, 1.0);
  int r = 255 * t;
  int b = 255 * (1.0 - t);

  for (int i = 0; i < 5; i++) {
    carrier.leds.setPixelColor(i, r, 0, b);
  }
  carrier.leds.setBrightness(brightness);
  carrier.leds.show();
}



