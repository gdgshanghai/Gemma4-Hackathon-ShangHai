#include <Arduino.h>
#include "bluetooth_manager.h"
#include "display_ui.h"
#include "pir_sensor.h"
#include "plant_controller.h"
#include "touch_feedback.h"
#include "wifi_time.h"
#include "web_server.h"
#include "camera_manager.h"
#include "soil_sensor.h"
#include "temperature_sensor.h"

namespace {
constexpr bool ENABLE_BLE_AT_BOOT = false;
}

void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("\n--- Smart Planter System Booting ---");

    initDisplay();
    delay(500);

    initWifiTime();
    printWifiStatus();

    if (ENABLE_BLE_AT_BOOT) {
        initBluetoothManager();
    } else {
        Serial.println("Boot Stage 3: BLE skipped to avoid startup freeze");
    }

    initPlantController();
    initPirSensor();
    initTouchFeedback();
    initSoilSensor();
    initTemperatureSensor();

    initWebServer();

    if (!initCamera()) {
        Serial.println("Warning: Camera failed to initialize.");
    }

    Serial.println("Environment Source: Soil & Temperature sensors active");
    Serial.println("All Modules Ready.");
    showNormalFace();
}

void loop() {
    handleTouchFeedback();
    handlePirWakeup();
    if (ENABLE_BLE_AT_BOOT) {
        updateBluetoothManager();
    }
    updateWifiTime();
    updateSoilSensor();
    updateTemperatureSensor();
    tickPlantController();
    handleWebServer();
    delay(10);
}
