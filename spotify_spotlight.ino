/*
=========================================================
Spotify IoT Arduino Client
=========================================================

Hardware:
- Arduino MKR WiFi 1010
- MKR IoT Carrier

Purpose:
- Connect to Arduino IoT Cloud
- Communicate with a Flask-based Spotify server
- Control Spotify playback (next, previous, play/pause)
- Display "Now Playing" info on the carrier screen
- Render smooth scrolling song/artist text
- Drive RGB LEDs based on Spotify + sensor context

Server:
- Flask server running on a laptop
- Endpoints: /update_context, /playpause, /next, /previous, /volume

Author: Philip Kwan
=========================================================
*/

#include <Arduino_MKRIoTCarrier.h>
#include <WiFiNINA.h>
#include <ArduinoHttpClient.h>
#include <ArduinoJson.h>
#include "arduino_secrets.h"

// Arduino IoT Cloud auto-generated properties
#include "thingProperties.h"

// ======================================================
// FLASK SERVER CONFIGURATION
// ======================================================
IPAddress serverIP(192, 168, 1, 157);  // Laptop running Flask
int serverPort = 5000;

WiFiClient wifi;
HttpClient client(wifi, serverIP, serverPort);
MKRIoTCarrier carrier;

// ======================================================
// TIMERS
// ======================================================
unsigned long lastTempCheck = 0;
const long interval = 10000;  // sensor + server update interval (ms)

// ======================================================
// LED PATTERN STATE
// ======================================================
unsigned long lastPatternTick = 0;
bool patternOn = false;

// ======================================================
// NOW PLAYING STATE
// ======================================================
String currentSong = "No Song";
String currentArtist = "";
bool isPlaying = true;

// ======================================================
// SMOOTH SCROLLING STATE (FIXED SINGLE CLOCK)
// ======================================================
float scrollPos = 0.0f;
unsigned long lastScrollUpdateMs = 0;
const float SCROLL_PX_PER_SEC = 55.0f;
const int TEXT_SIZE = 2;

// ======================================================
// SCREEN LAYOUT CONSTANTS
// ======================================================
const int SCREEN_W = 240;
const int SCREEN_H = 240;

const int HUD_Y = 170;     // bottom UI area
const int HUD_H = 70;
const int LEFT_PAD = 8;
const int ICON_W = 32;

// Text band (only this area is cleared to prevent flicker)
const int TEXT_Y = HUD_Y + 22;
const int TEXT_BAND_Y = HUD_Y + 18;
const int TEXT_BAND_H = 28;

// Play/pause icon Y position
const int ICON_Y = HUD_Y + 12;

// Cached values to prevent unnecessary redraws
String lastLine = "";
bool lastIsPlaying = true;

// ======================================================
// FORWARD DECLARATIONS
// ======================================================
void sendRequest(String endpoint);
void parseResponse(String jsonResponse);
void flashLED(int r, int g, int b);
void updateLocalPattern(int r, int g, int b, String pat, int periodMs);

// UI helpers
int approxTextWidthPx(const String &s, int textSize);
void drawPlayPauseIcon(bool playing, bool forceRedraw);
void drawScrollingNowPlaying(bool forceRedraw);
void drawHUD(bool forceRedraw);

// ======================================================
// CLOUD COLOR HELPER
// ======================================================
void getCloudColor(int &r, int &g, int &b) {
  // Retrieve color selected in Arduino IoT Cloud
  Color c = light_color.getValue();

  uint8_t rr, gg, bb;
  c.getRGB(rr, gg, bb);

  r = (int)rr;
  g = (int)gg;
  b = (int)bb;

  // Default fallback color
  if (r == 0 && g == 0 && b == 0) {
    r = 0; g = 0; b = 255;
  }
}

// ======================================================
// ARDUINO IOT CLOUD CALLBACKS
// ======================================================
void onCloudNextChange() {
  if (cloud_next) {
    sendRequest("/next");
    cloud_next = false;
  }
}

void onCloudPrevChange() {
  if (cloud_prev) {
    sendRequest("/previous");
    cloud_prev = false;
  }
}

void onCloudPlaypauseChange() {
  if (cloud_playpause) {
    sendRequest("/playpause");
    cloud_playpause = false;
  }
}

void onVolumeSwitchChange() {
  int v = constrain(volume_switch, 0, 100);
  sendRequest("/volume?set=" + String(v));
}

void onPowerSwitchChange() {
  if (!power_Switch) {
    // Power OFF: clear LEDs and screen
    carrier.leds.fill(carrier.leds.Color(0, 0, 0), 0, 5);
    carrier.leds.show();
    carrier.display.fillScreen(ST77XX_BLACK);
  } else {
    // Power ON: force clean HUD redraw
    lastLine = "";
    lastIsPlaying = !isPlaying;
  }
}

void onLEDSwitchChange() {
  if (!lED_Switch) {
    carrier.leds.fill(carrier.leds.Color(0, 0, 0), 0, 5);
    carrier.leds.show();
  }
}

// No-op callbacks required by IoT Cloud
void onLightModeChange() {}
void onLightColorChange() {}
void onPatternChange() {}
void onPatternPeriodMsChange() {}

// ======================================================
// SETUP
// ======================================================
void setup() {
  Serial.begin(9600);

  CARRIER_CASE = true;
  if (!carrier.begin()) {
    Serial.println("Carrier not connected");
    while (1);
  }

  // Initialize IoT Cloud
  initProperties();
  ArduinoCloud.begin(ArduinoIoTPreferredConnection);

  // Default values
  if (light_mode.length() == 0) light_mode = "TEMP";
  if (pattern.length() == 0) pattern = "PULSE";
  if (pattern_period_ms == 0) pattern_period_ms = 900;

  cloud_next = false;
  cloud_prev = false;
  cloud_playpause = false;

  // Initial display
  carrier.display.fillScreen(ST77XX_BLACK);
  carrier.display.setTextWrap(false);

  carrier.display.setCursor(20, 60);
  carrier.display.setTextSize(2);
  carrier.display.setTextColor(ST77XX_WHITE);
  carrier.display.print("Spotify IoT");

  // Draw HUD background
  carrier.display.fillRect(0, HUD_Y, SCREEN_W, HUD_H, ST77XX_BLACK);

  lastScrollUpdateMs = millis();
}

// ======================================================
// MAIN LOOP
// ======================================================
void loop() {
  ArduinoCloud.update();
  carrier.Buttons.update();

  // Touch controls
  if (carrier.Buttons.onTouchDown(TOUCH0)) {
    sendRequest("/previous");
    flashLED(255, 0, 0);
  }
  if (carrier.Buttons.onTouchDown(TOUCH2)) {
    sendRequest("/playpause");
    flashLED(0, 255, 0);
  }
  if (carrier.Buttons.onTouchDown(TOUCH4)) {
    sendRequest("/next");
    flashLED(0, 0, 255);
  }

  // Periodic sensor + context update
  unsigned long now = millis();
  if (now - lastTempCheck >= interval) {
    lastTempCheck = now;

    float temperature = carrier.Env.readTemperature();
    float humidity = carrier.Env.readHumidity();

    int r, g, b;
    getCloudColor(r, g, b);

    String endpoint =
      "/update_context?temp=" + String(temperature, 2) +
      "&hum=" + String(humidity, 2) +
      "&mode=" + light_mode +
      "&cr=" + String(r) +
      "&cg=" + String(g) +
      "&cb=" + String(b) +
      "&pattern=" + pattern +
      "&periodMs=" + String(pattern_period_ms);

    sendRequest(endpoint);
  }

  // LED pattern animation
  if (power_Switch && lED_Switch && light_mode == "PATTERN") {
    int r, g, b;
    getCloudColor(r, g, b);
    updateLocalPattern(r, g, b, pattern, pattern_period_ms);
  }

  // Non-blocking UI redraw
  if (power_Switch) {
    drawHUD(false);
  }
}

// ======================================================
// HTTP + JSON HANDLING
// ======================================================
void sendRequest(String endpoint) {
  client.get(endpoint);
  if (client.responseStatusCode() == 200) {
    parseResponse(client.responseBody());
  }
}

void parseResponse(String jsonResponse) {
  StaticJsonDocument<1024> doc;
  if (deserializeJson(doc, jsonResponse)) return;

  int r = doc["r"] | 0;
  int g = doc["g"] | 0;
  int b = doc["b"] | 0;

  if (doc.containsKey("song"))   currentSong = doc["song"].as<String>();
  if (doc.containsKey("artist")) currentArtist = doc["artist"].as<String>();
  if (doc.containsKey("is_playing")) isPlaying = doc["is_playing"].as<bool>();

  if (!power_Switch || !lED_Switch) {
    carrier.leds.fill(carrier.leds.Color(0, 0, 0), 0, 5);
    carrier.leds.show();
    return;
  }

  if (light_mode != "PATTERN") {
    carrier.leds.fill(carrier.leds.Color(r, g, b), 0, 5);
    carrier.leds.show();
  }

  drawHUD(true);
}

// ======================================================
// UI HELPERS
// ======================================================
int approxTextWidthPx(const String &s, int textSize) {
  return s.length() * 6 * textSize;
}

void drawPlayPauseIcon(bool playing, bool forceRedraw) {
  if (!forceRedraw && playing == lastIsPlaying) return;

  int x = SCREEN_W - ICON_W;
  carrier.display.fillRect(x, HUD_Y, ICON_W, HUD_H, ST77XX_BLACK);

  if (playing) {
    carrier.display.fillRect(x + 8,  ICON_Y + 4, 6, 26, ST77XX_WHITE);
    carrier.display.fillRect(x + 18, ICON_Y + 4, 6, 26, ST77XX_WHITE);
  } else {
    carrier.display.fillTriangle(
      x + 8, ICON_Y + 2,
      x + 8, ICON_Y + 32,
      x + 26, ICON_Y + 17,
      ST77XX_WHITE
    );
  }

  lastIsPlaying = playing;
}

void drawScrollingNowPlaying(bool forceRedraw) {
  String line = currentSong;
  if (currentArtist.length() > 0) line += " - " + currentArtist;

  int availW = SCREEN_W - ICON_W - (LEFT_PAD * 2);
  int textW  = approxTextWidthPx(line, TEXT_SIZE);

  if (forceRedraw || line != lastLine) {
    lastLine = line;
    scrollPos = 0;
    lastScrollUpdateMs = millis();
  }

  carrier.display.fillRect(0, TEXT_BAND_Y, SCREEN_W - ICON_W, TEXT_BAND_H, ST77XX_BLACK);

  carrier.display.setTextSize(TEXT_SIZE);
  carrier.display.setTextColor(ST77XX_WHITE);
  carrier.display.setTextWrap(false);

  if (textW <= availW) {
    carrier.display.setCursor(LEFT_PAD, TEXT_Y);
    carrier.display.print(line);
    return;
  }

  unsigned long now = millis();
  float dt = (now - lastScrollUpdateMs) / 1000.0f;
  lastScrollUpdateMs = now;
  scrollPos += SCROLL_PX_PER_SEC * dt;

  const int gapPx = 40;
  float loopLen = textW + gapPx;
  if (scrollPos >= loopLen) scrollPos -= loopLen;

  int x = (int)(-scrollPos);
  carrier.display.setCursor(LEFT_PAD + x, TEXT_Y);
  carrier.display.print(line);
  carrier.display.setCursor(LEFT_PAD + x + textW + gapPx, TEXT_Y);
  carrier.display.print(line);
}

void drawHUD(bool forceRedraw) {
  drawPlayPauseIcon(isPlaying, forceRedraw);
  drawScrollingNowPlaying(forceRedraw);
}

// ======================================================
// LED HELPERS
// ======================================================
void updateLocalPattern(int r, int g, int b, String pat, int periodMs) {
  if (millis() - lastPatternTick >= (unsigned long)max(100, periodMs)) {
    lastPatternTick = millis();
    patternOn = !patternOn;

    if (pat == "BLINK") {
      carrier.leds.fill(
        carrier.leds.Color(patternOn ? r : 0, patternOn ? g : 0, patternOn ? b : 0),
        0, 5
      );
    } else {
      carrier.leds.fill(
        carrier.leds.Color(patternOn ? r : r / 6, patternOn ? g : g / 6, patternOn ? b : b / 6),
        0, 5
      );
    }
    carrier.leds.show();
  }
}

void flashLED(int r, int g, int b) {
  if (!power_Switch || !lED_Switch) return;
  carrier.leds.fill(carrier.leds.Color(r, g, b), 0, 5);
  carrier.leds.show();
  delay(150);
  carrier.leds.fill(carrier.leds.Color(0, 0, 0), 0, 5);
  carrier.leds.show();
}
