#include "pir_sensor.h"
#include "hardware_config.h"
#include "plant_controller.h"

namespace {
const unsigned long PIR_RETRIGGER_MS = 1500;

const char* const IR_LINES[] = {
    "你来啦!", "好想你呀~", "为你亮灯!", "又见面啦~",
    "加油哦!", "你是我的阳光~", "一起成长!"
};

bool lastPirState = LOW;
unsigned long lastPirTriggerTime = 0;

const char* pickRandomLine(const char* const* lines, size_t count) {
    return lines[random(count)];
}
}  // namespace

void initPirSensor() {
    pinMode(PIR_PIN, INPUT);
    lastPirState = digitalRead(PIR_PIN) == HIGH;
}

void handlePirWakeup() {
    bool pirState = digitalRead(PIR_PIN) == HIGH;

    if (pirState && !lastPirState && millis() - lastPirTriggerTime >= PIR_RETRIGGER_MS) {
        lastPirTriggerTime = millis();
        noteInteraction();

        const char* irLine = pickRandomLine(IR_LINES, sizeof(IR_LINES) / sizeof(IR_LINES[0]));
        if (isPlantSleeping()) {
            wakePlant(irLine);
        } else {
            showBubble(irLine);
        }

        Serial.println("Trigger: PIR Wakeup");
    }

    lastPirState = pirState;
}
