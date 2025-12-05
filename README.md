# Spotify Spotlight

> MKR IoT Carrier + Flask + Spotify API

## 📖 Overview

This project connects a Spotify account to an **Arduino MKR IoT Carrier**. A Python Flask backend talks to the Spotify Web API and acts as a bridge. The Arduino polls the backend to send temperature data and receive song info + color codes, while the capacitive buttons on the Carrier control music playback.

---

## 🏗️ Architecture Overview

### 🎵 Spotify Web API
- Provides user playback information and audio features (energy, valence)
- Uses the OAuth 2.0 authorization code flow

### 💻 Python Flask Backend (Laptop)

**Authentication:**
- Handles Spotify login via a local browser popup (`http://127.0.0.1:8888/callback`)

**Logic Engine:**
- Receives temperature from Arduino
- Fetches song energy from Spotify
- Calculates the specific RGB color values (Red/Yellow for hot, Blue/Teal for cold)

**Endpoints:**
- `/update_context?temp=XX` - Returns JSON with Song Name, Artist, and RGB values
- `/next` - Next track
- `/previous` - Previous track
- `/playpause` - Play/Pause toggle

### 🤖 Arduino MKR IoT Carrier

- **Network:** Connects to the same Wi-Fi network as the laptop
- **Input:** Capacitive touch buttons send commands to Flask
- **Sensors:** Reads ambient temperature and sends it to the server
- **Output:** Updates the display with song info and sets LEDs to the RGB values calculated by the server

---

## ✅ Prerequisites

- ✨ Spotify Premium account (required for playback control)
- 🔑 Spotify Developer account and App (Client ID/Secret)
- 🐍 Python 3 + pip
- 🔌 Arduino MKR WiFi 1010 + MKR IoT Carrier
- 📡 A personal Wi-Fi hotspot (Recommended for device-to-device communication)

---

## 🚀 Setup

### 1. Spotify Developer Configuration

1. Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Copy the **Client ID** and **Client Secret**
3. Add this exact **Redirect URI** in the settings:
   ```
   http://127.0.0.1:8888/callback
   ```
   > **Note:** This is for the laptop's browser authentication

### 2. Python Backend

1. Clone or download this repository

2. Create a `.env` file in the project folder:
   ```env
   SPOTIPY_CLIENT_ID=your_client_id_here
   SPOTIPY_CLIENT_SECRET=your_client_secret_here
   SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
   ```

3. Install dependencies:
   ```bash
   pip install flask spotipy python-dotenv
   ```

4. Run the server:
   ```bash
   python app.py
   ```

5. Follow the prompt in the terminal to log in via your browser

6. Once authenticated, the server runs on `0.0.0.0:5000`. Note your laptop's **LAN IP Address** (e.g., `192.168.1.157`)

### 3. Arduino Configuration

1. Open the Arduino IDE

2. Create a tab named `arduino_secrets.h`:
   ```cpp
   #define SECRET_SSID  "your-hotspot-ssid"
   #define SECRET_PASS  "your-hotspot-password"
   ```

3. In the main sketch, update the `serverIP` to match your laptop's LAN IP:
   ```cpp
   IPAddress serverIP(192, 168, 1, 157); // UPDATE THIS
   ```

4. Upload the sketch to the MKR WiFi 1010

---

## 🎮 Running the System

1. **Laptop:** Ensure `app.py` is running and says "Server is listening"
2. **Spotify:** Open Spotify on your laptop/phone and play a track manually (to wake up the device)
3. **Arduino:** Power it on
4. **Loop:** Every 10 seconds, it sends temp to the laptop and updates the LEDs/Screen

### Button Controls

| Button | Function |
|--------|----------|
| Button 0 | Previous Track |
| Button 2 | Play/Pause |
| Button 4 | Next Track |

---

## 🔧 Troubleshooting

### "Connection Failed" on Arduino

- ✅ Ensure Laptop and Arduino are on the **exact same WiFi**
- ✅ Check if Windows Firewall is blocking **Port 5000** (Try turning off Private Network Firewall temporarily)
- ✅ Verify the IP address in the Arduino sketch matches `ipconfig` on the laptop

### "Spotify Error: Code must be supplied"

- This happens during login if the Redirect URI doesn't match
- ✅ Ensure the `.env` file and Spotify Dashboard both use `http://127.0.0.1:8888/callback`

---

## 📝 Arduino Sketch Reference

Use this code for the MKR WiFi 1010:

## 📝 Arduino Sketch Reference

Use this code for the MKR WiFi 1010:

```cpp
/* Spotify Spotlight - Group Project */
#include <Arduino_MKRIoTCarrier.h>
#include <WiFiNINA.h>
#include <ArduinoHttpClient.h>
#include <ArduinoJson.h>
#include "arduino_secrets.h" 

MKRIoTCarrier carrier;

char ssid[] = SECRET_SSID;
char pass[] = SECRET_PASS;

// UPDATE THIS TO YOUR LAPTOP'S IP ADDRESS
IPAddress serverIP(192, 168, 1, 157); 
int serverPort = 5000;

WiFiClient wifi;
HttpClient client = HttpClient(wifi, serverIP, serverPort);

unsigned long lastCheck = 0;
const long interval = 2000; // Check context every 2 seconds

void setup() {
  Serial.begin(9600);
  
  // Set to false if using the board without the plastic case
  CARRIER_CASE = true; 
  if (!carrier.begin()) {
    Serial.println("Carrier not connected");
    while (1);
  }

  // Connect to WiFi
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print("Connecting to ");
    Serial.println(ssid);
    WiFi.begin(ssid, pass);
    delay(1000);
  }
  Serial.println("Connected to WiFi");
  
  carrier.display.fillScreen(ST77XX_BLACK);
  carrier.display.setRotation(0);
  carrier.display.setTextColor(ST77XX_WHITE);
  carrier.display.setTextSize(2);
  carrier.display.setCursor(20, 100);
  carrier.display.print("Spotify IoT");
}

void loop() {
  // Update touch buttons
  carrier.Buttons.update();

  // --- CONTROLS ---
  if (carrier.Buttons.onTouchDown(TOUCH0)) {
    sendRequest("/previous");
  }

  if (carrier.Buttons.onTouchDown(TOUCH2)) {
    sendRequest("/playpause");
  }

  if (carrier.Buttons.onTouchDown(TOUCH4)) {
    sendRequest("/next");
  }

  // --- DATA LOOP ---
  if (millis() - lastCheck >= interval) {
    lastCheck = millis();
    
    float temperature = carrier.Env.readTemperature();
    
    // Build the request: /update_context?temp=25.5
    String url = "/update_context?temp=" + String(temperature);
    
    client.get(url);
    int statusCode = client.responseStatusCode();
    String response = client.responseBody();

    if(statusCode == 200) {
      parseAndDisplay(response);
    } else {
      Serial.print("Error: "); Serial.println(statusCode);
    }
  }
}

void sendRequest(String endpoint) {
  Serial.print("Sending: "); Serial.println(endpoint);
  client.get(endpoint);
  // We don't strictly need to parse the response for controls, just trigger it
  client.responseStatusCode(); 
  client.responseBody();
}

void parseAndDisplay(String json) {
  // Parse JSON
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, json);

  if (error) {
    Serial.println("JSON Parse Error");
    return;
  }

  const char* song = doc["song"];
  const char* artist = doc["artist"];
  int r = doc["r"];
  int g = doc["g"];
  int b = doc["b"];

  // Update Display
  carrier.display.fillScreen(ST77XX_BLACK);
  
  carrier.display.setTextSize(1);
  carrier.display.setCursor(20, 60);
  carrier.display.setTextColor(ST77XX_WHITE);
  carrier.display.println("NOW PLAYING:");
  
  carrier.display.setTextSize(2);
  carrier.display.setCursor(20, 80);
  // Set text color to match the calculated mood color
  carrier.display.setTextColor(carrier.display.color565(r, g, b));
  carrier.display.println(song);
  
  carrier.display.setTextSize(1);
  carrier.display.setCursor(20, 120);
  carrier.display.setTextColor(ST77XX_WHITE);
  carrier.display.println(artist);

  // Update LEDs
  carrier.leds.fill(carrier.leds.Color(r, g, b), 0, 5);
  carrier.leds.show();
}
```

---

## 📄 License

This project is open source. See the LICENSE file for details.

## 👥 Contributors

Group Project - INST347
