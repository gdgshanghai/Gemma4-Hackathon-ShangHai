#include "temperature_sensor.h"

#include <DallasTemperature.h>
#include <OneWire.h>

#include "hardware_config.h"
#include "plant_controller.h"

namespace {
const unsigned long TEMPERATURE_POLL_MS = 2000;

OneWire oneWire(TEMPERATURE_PIN);
DallasTemperature temperatureBus(&oneWire);
unsigned long lastTemperaturePollTime = 0;
bool temperatureAvailable = false;
int lastLoggedTemperature = 1000;

bool readTemperatureC(int& temperatureC) {
    temperatureBus.requestTemperatures();
    float tempC = temperatureBus.getTempCByIndex(0);

    if (tempC == DEVICE_DISCONNECTED_C || tempC < -55.0f || tempC > 125.0f) {
        return false;
    }

    temperatureC = static_cast<int>(tempC + (tempC >= 0 ? 0.5f : -0.5f));
    return true;
}
}  // namespace

void initTemperatureSensor() {
    pinMode(TEMPERATURE_PIN, INPUT_PULLUP);
    temperatureBus.begin();
    temperatureBus.setWaitForConversion(true);
    temperatureBus.setResolution(12);

    int initialTemperature = 25;
    temperatureAvailable = readTemperatureC(initialTemperature);
    setTemperatureC(initialTemperature);

    Serial.print("Temperature Sensor Pin: GPIO");
    Serial.println(TEMPERATURE_PIN);
    if (temperatureAvailable) {
        Serial.print("Temperature Sensor Initialized: ");
        Serial.print(initialTemperature);
        Serial.println("C");
        lastLoggedTemperature = initialTemperature;
    } else {
        Serial.println("Temperature Sensor Initialized: fallback 25C, read failed");
    }
}

void updateTemperatureSensor() {
    if (millis() - lastTemperaturePollTime < TEMPERATURE_POLL_MS) {
        return;
    }

    lastTemperaturePollTime = millis();

    int previousTemperature = getTemperatureC();
    int currentTemperature = previousTemperature;

    if (!readTemperatureC(currentTemperature)) {
        Serial.println("Temperature Sensor: read failed");
        return;
    }

    temperatureAvailable = true;
    setTemperatureC(currentTemperature);

    if (currentTemperature != lastLoggedTemperature) {
        Serial.print("Temperature Sensor Update: ");
        Serial.print(currentTemperature);
        Serial.println("C");
        lastLoggedTemperature = currentTemperature;
    }

    if (isPlantSleeping()) {
        return;
    }

    if (abs(previousTemperature - currentTemperature) >= 1) {
        renderAwakePlant();
    }
}
