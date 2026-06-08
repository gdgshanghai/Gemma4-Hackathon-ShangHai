#include "wifi_time.h"

#include <Arduino.h>
#include <WiFi.h>
#include <stddef.h>
#include <time.h>

namespace {
#if defined(__has_include)
#if __has_include("wifi_credentials.h")
#include "wifi_credentials.h"
#define WIFI_CREDENTIALS_AVAILABLE 1
#else
#define WIFI_CREDENTIALS_AVAILABLE 0
#endif
#else
#define WIFI_CREDENTIALS_AVAILABLE 0
#endif

struct WifiCredential {
    const char* ssid;
    const char* password;
};

#if WIFI_CREDENTIALS_AVAILABLE
const WifiCredential kWifiCredentials[] = {WIFI_CREDENTIALS};
#else
const WifiCredential kWifiCredentials[] = {};
#endif

const char* NTP_SERVER_1 = "ntp.aliyun.com";
const char* NTP_SERVER_2 = "pool.ntp.org";
const long GMT_OFFSET_SECONDS = 8 * 3600;
const int DAYLIGHT_OFFSET_SECONDS = 0;

const unsigned long WIFI_RETRY_INTERVAL_MS = 15000;
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 8000;

unsigned long lastWifiAttemptTime = 0;
unsigned long wifiConnectStartTime = 0;
bool ntpConfigured = false;
size_t currentSsidIndex = 0;
bool connecting = false;
bool loggedWifiConfigHint = false;

constexpr size_t kWifiCredentialCount =
    sizeof(kWifiCredentials) / sizeof(kWifiCredentials[0]);

bool hasWifiCredentials() {
    return kWifiCredentialCount > 0;
}

const WifiCredential* getCurrentCredential() {
#if WIFI_CREDENTIALS_AVAILABLE
    if (!hasWifiCredentials()) {
        return nullptr;
    }
#if 1
    return &kWifiCredentials[currentSsidIndex % kWifiCredentialCount];
#endif
#else
    return nullptr;
#endif
}

void moveToNextCredential() {
#if WIFI_CREDENTIALS_AVAILABLE
    if (!hasWifiCredentials()) {
        return;
    }
#if 1
    currentSsidIndex = (currentSsidIndex + 1) % kWifiCredentialCount;
#endif
#else
    currentSsidIndex = 0;
#endif
}

bool getMillisFallbackTime(char* buffer, int bufferSize) {
    if (buffer == nullptr || bufferSize < 6) {
        return false;
    }

    unsigned long totalSeconds = millis() / 1000UL;
    unsigned int hours = (totalSeconds / 3600UL) % 24;
    unsigned int minutes = (totalSeconds / 60UL) % 60;
    snprintf(buffer, bufferSize, "%02u:%02u", hours, minutes);
    return true;
}

void configureNtpIfNeeded() {
    if (ntpConfigured || WiFi.status() != WL_CONNECTED) {
        return;
    }

    configTime(GMT_OFFSET_SECONDS, DAYLIGHT_OFFSET_SECONDS, NTP_SERVER_1, NTP_SERVER_2);
    ntpConfigured = true;
    Serial.println("WiFi Time: NTP configured");
}

void attemptWifiConnect(bool blocking) {
    if (!hasWifiCredentials()) {
        if (!loggedWifiConfigHint) {
            Serial.println(
                "WiFi Time: wifi_credentials.h not found, running in offline mode"
            );
            loggedWifiConfigHint = true;
        }
        connecting = false;
        return;
    }

    if (WiFi.status() == WL_CONNECTED) {
        connecting = false;
        configureNtpIfNeeded();
        return;
    }

    unsigned long now = millis();
    
    // Check if current connection attempt timed out
    if (connecting && now - wifiConnectStartTime >= WIFI_CONNECT_TIMEOUT_MS) {
        Serial.println("WiFi Time: connection timeout, switching network");
        moveToNextCredential();
        connecting = false;
        lastWifiAttemptTime = 0; // Allow immediate retry on next network
    }
    
    if (!blocking && !connecting && now - lastWifiAttemptTime < WIFI_RETRY_INTERVAL_MS) {
        return;
    }

    if (!connecting) {
        const WifiCredential* credential = getCurrentCredential();
        if (credential == nullptr) {
            return;
        }

        lastWifiAttemptTime = now;
        wifiConnectStartTime = now;
        connecting = true;
        
        WiFi.mode(WIFI_STA);
        WiFi.setSleep(false);
        WiFi.setAutoReconnect(true);
        
        WiFi.begin(credential->ssid, credential->password);
        Serial.print("WiFi Time: connecting to ");
        Serial.print(credential->ssid);
        Serial.print(" (priority ");
        Serial.print(currentSsidIndex + 1);
        Serial.println(")");
    }

    if (!blocking) {
        return;
    }

    // Blocking wait
    while (WiFi.status() != WL_CONNECTED && millis() - wifiConnectStartTime < WIFI_CONNECT_TIMEOUT_MS) {
        delay(250);
    }

    if (WiFi.status() == WL_CONNECTED) {
        const WifiCredential* credential = getCurrentCredential();
        connecting = false;
        Serial.print("WiFi Time: connected to ");
        Serial.println(credential != nullptr ? credential->ssid : "UNKNOWN");
        Serial.print("WiFi Time: IP=");
        Serial.println(WiFi.localIP());
        configureNtpIfNeeded();
    } else {
        Serial.println("WiFi Time: connection timeout, trying next network");
        moveToNextCredential();
        connecting = false;
    }
}
}  // namespace

void initWifiTime() {
    attemptWifiConnect(true);
}

void updateWifiTime() {
    if (WiFi.status() == WL_CONNECTED) {
        configureNtpIfNeeded();
        return;
    }

    ntpConfigured = false;
    attemptWifiConnect(false);
}

bool getFormattedTime(char* buffer, int bufferSize) {
    if (buffer == nullptr || bufferSize < 6) {
        return false;
    }

    struct tm timeInfo;
    if (WiFi.status() == WL_CONNECTED && getLocalTime(&timeInfo, 50)) {
        strftime(buffer, bufferSize, "%H:%M", &timeInfo);
        return true;
    }

    return getMillisFallbackTime(buffer, bufferSize);
}

void printWifiStatus() {
    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("WiFi Time: current IP=");
        Serial.println(WiFi.localIP());
        return;
    }

    Serial.println("WiFi Time: current IP=DISCONNECTED");
}

void getLocalIPStr(char* buffer, int bufferSize) {
    if (WiFi.status() == WL_CONNECTED) {
        snprintf(buffer, bufferSize, "%s", WiFi.localIP().toString().c_str());
    } else {
        snprintf(buffer, bufferSize, "DISCONNECTED");
    }
}
