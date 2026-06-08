#ifndef HARDWARE_CONFIG_H
#define HARDWARE_CONFIG_H

#include <Arduino.h>

constexpr int TOUCH_PIN = 2;
constexpr int PIR_PIN = 40;
constexpr int MOISTURE_PIN = 16;
constexpr int TEMPERATURE_PIN = 4;
constexpr int LED_PIN = 48;

// Camera Pins (GC0308 / 8225N v2.0) - Safer Pins for S3 Octal PSRAM (Avoiding Strapping Pins 0, 45, 46)
constexpr int CAM_PIN_PWDN = -1;
constexpr int CAM_PIN_RESET = -1;
constexpr int CAM_PIN_XCLK = 15;
constexpr int CAM_PIN_SIOD = 42;
constexpr int CAM_PIN_SIOC = 41;

constexpr int CAM_PIN_D7 = 17;
constexpr int CAM_PIN_D6 = 18;
constexpr int CAM_PIN_D5 = 21;
constexpr int CAM_PIN_D4 = 47;
constexpr int CAM_PIN_D3 = 8;
constexpr int CAM_PIN_D2 = 7;
constexpr int CAM_PIN_D1 = 6;
constexpr int CAM_PIN_D0 = 5;
constexpr int CAM_PIN_VSYNC = 3;
constexpr int CAM_PIN_HREF = 1;
constexpr int CAM_PIN_PCLK = 13;

constexpr int MOISTURE_RAW_WET = 1200;
constexpr int MOISTURE_RAW_DRY = 2800;
constexpr int MOISTURE_RAW_DROWN_WARNING = 1400;
constexpr int MOISTURE_RAW_DROWN_DANGER = 1000;
constexpr int MOISTURE_RAW_THIRST_WARNING = 2300;
constexpr int MOISTURE_RAW_THIRST_DANGER = 2700;

#endif
