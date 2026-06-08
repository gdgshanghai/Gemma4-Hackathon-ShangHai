#include "soil_sensor.h"
#include "hardware_config.h"
#include "plant_controller.h"

namespace {
const unsigned long SENSOR_POLL_MS = 800;
const unsigned long SENSOR_LOG_MS = 3000;

unsigned long lastSensorPollTime = 0;
unsigned long lastSensorLogTime = 0;
int lastLoggedRaw = -1;

int readMoistureRaw() {
    long rawSum = 0;
    for (int i = 0; i < 4; ++i) {
        rawSum += analogRead(MOISTURE_PIN);
        delayMicroseconds(200);
    }

    return rawSum / 4;
}

}  // namespace

void initSoilSensor() {
    pinMode(MOISTURE_PIN, INPUT);
    analogReadResolution(12);
    analogSetPinAttenuation(MOISTURE_PIN, ADC_11db);

    int raw = readMoistureRaw();
    setMoistureRaw(raw);

    Serial.print("Soil Sensor Initialized: GPIO");
    Serial.print(MOISTURE_PIN);
    Serial.print(", raw=");
    Serial.print(raw);
    Serial.println();
}

void updateSoilSensor() {
    if (millis() - lastSensorPollTime < SENSOR_POLL_MS) {
        return;
    }

    lastSensorPollTime = millis();

    int previousMoisture = getMoistureRaw();
    int raw = readMoistureRaw();
    setMoistureRaw(raw);

    if (millis() - lastSensorLogTime >= SENSOR_LOG_MS || abs(raw - lastLoggedRaw) >= 40) {
        lastSensorLogTime = millis();
        lastLoggedRaw = raw;
        Serial.print("Soil Sensor Update: raw=");
        Serial.println(raw);
    }

    if (isPlantSleeping()) {
        return;
    }

    int currentMoisture = getMoistureRaw();

    if (abs(previousMoisture - currentMoisture) >= 40) {
        renderAwakePlant();
    }
}
