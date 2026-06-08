#include "touch_feedback.h"
#include "display_ui.h"
#include "hardware_config.h"
#include "plant_controller.h"

namespace {
const unsigned long TOUCH_DEBOUNCE_MS = 50;
const unsigned long LONG_PRESS_THRESHOLD = 2000;
const unsigned long TOUCH_RELEASE_GUARD_MS = 120;
const unsigned long DIALOG_FRAME_MS = 220;

unsigned long pressStartTime = 0;
unsigned long lastTouchChangeTime = 0;
unsigned long lastReleaseTime = 0;
unsigned long lastDialogFrameTime = 0;
bool isPressed = false;
bool isLongPressHandled = false;
bool requireReleaseBeforeNextPress = false;
bool isDialogModeActive = false;
int lastRawTouchState = LOW;
int stableTouchState = LOW;
int touchIdleLevel = LOW;
int touchActiveLevel = HIGH;
uint8_t dialogFrame = 0;

int detectIdleTouchLevel() {
    int highCount = 0;
    int lowCount = 0;

    for (int i = 0; i < 12; ++i) {
        int value = digitalRead(TOUCH_PIN);
        if (value == HIGH) {
            ++highCount;
        } else {
            ++lowCount;
        }
        delay(10);
    }

    return (highCount > lowCount) ? HIGH : LOW;
}

bool isTouchActiveState(int state) {
    return state == touchActiveLevel;
}

bool isTouchIdleState(int state) {
    return state == touchIdleLevel;
}

int readStableTouchState() {
    int rawTouchState = digitalRead(TOUCH_PIN);

    if (rawTouchState != lastRawTouchState) {
        lastRawTouchState = rawTouchState;
        lastTouchChangeTime = millis();
    }

    if ((millis() - lastTouchChangeTime) >= TOUCH_DEBOUNCE_MS) {
        stableTouchState = rawTouchState;
    }

    return stableTouchState;
}

void resetPressState() {
    isPressed = false;
    isLongPressHandled = false;
    pressStartTime = 0;
    digitalWrite(LED_PIN, LOW);
}

void startDialogMode() {
    isDialogModeActive = true;
    dialogFrame = 0;
    lastDialogFrameTime = millis();
    clearBubble();
    showDialogAnimationFrame(dialogFrame);
}

void stopDialogMode() {
    isDialogModeActive = false;
    dialogFrame = 0;
    lastDialogFrameTime = 0;
}

void updateDialogAnimation() {
    if (!isDialogModeActive || isPlantSleeping()) {
        return;
    }

    if (millis() - lastDialogFrameTime >= DIALOG_FRAME_MS) {
        lastDialogFrameTime = millis();
        dialogFrame = (dialogFrame + 1) % 4;
        showDialogAnimationFrame(dialogFrame);
    }
}
}  // namespace

void initTouchFeedback() {
    pinMode(TOUCH_PIN, INPUT);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    touchIdleLevel = detectIdleTouchLevel();
    touchActiveLevel = (touchIdleLevel == HIGH) ? LOW : HIGH;

    lastRawTouchState = digitalRead(TOUCH_PIN);
    stableTouchState = lastRawTouchState;
    lastTouchChangeTime = millis();
    lastReleaseTime = millis();
    Serial.print("Touch Module Initialized. idle=");
    Serial.print(touchIdleLevel == HIGH ? "HIGH" : "LOW");
    Serial.print(", active=");
    Serial.println(touchActiveLevel == HIGH ? "HIGH" : "LOW");
}

void handleTouchFeedback() {
    int touchState = readStableTouchState();
    updateDialogAnimation();

    if (requireReleaseBeforeNextPress) {
        if (isTouchIdleState(touchState)) {
            requireReleaseBeforeNextPress = false;
            resetPressState();
            lastReleaseTime = millis();
            Serial.println("Touch Gate: Release detected, input re-armed");
        }
        return;
    }

    if (isTouchIdleState(touchState)) {
        lastReleaseTime = millis();
    }

    if (isDialogModeActive) {
        if (isTouchActiveState(touchState) && !isPressed) {
            if (millis() - lastReleaseTime < TOUCH_RELEASE_GUARD_MS) {
                return;
            }
            isPressed = true;
            pressStartTime = millis();
            isLongPressHandled = false;
            digitalWrite(LED_PIN, HIGH);
            noteInteraction();
        } else if (isTouchIdleState(touchState) && isPressed) {
            resetPressState();
            lastReleaseTime = millis();
            stopDialogMode();
            Serial.println("Dialog Mode: Click to exit");
            renderAwakePlant();
            noteInteraction();
        }
        return;
    }

    if (isTouchActiveState(touchState) && !isPressed) {
        if (millis() - lastReleaseTime < TOUCH_RELEASE_GUARD_MS) {
            return;
        }

        if (isPlantSleeping()) {
            wakePlant();
            requireReleaseBeforeNextPress = true;
            resetPressState();
            noteInteraction();
            return;
        }

        isPressed = true;
        pressStartTime = millis();
        isLongPressHandled = false;
        digitalWrite(LED_PIN, HIGH);
        noteInteraction();
    }
    else if (isTouchActiveState(touchState) && isPressed) {
        if (!isLongPressHandled && (millis() - pressStartTime >= LONG_PRESS_THRESHOLD)) {
            isLongPressHandled = true;
            digitalWrite(LED_PIN, LOW);
            clearBubble();
            Serial.println("Trigger: Long Press (Dialog Mode)");
            startDialogMode();
            requireReleaseBeforeNextPress = true;
            noteInteraction();
        }
    }
    else if (isTouchIdleState(touchState) && isPressed) {
        // 短按逻辑
        digitalWrite(LED_PIN, LOW);
        if (!isLongPressHandled) {
            Serial.println("Trigger: Short Press (Happy Animation)");
            triggerShortPressAction();
            noteInteraction();
        }
        resetPressState();
        lastReleaseTime = millis();
    }
}

bool isTouchDialogModeActive() {
    return isDialogModeActive;
}
