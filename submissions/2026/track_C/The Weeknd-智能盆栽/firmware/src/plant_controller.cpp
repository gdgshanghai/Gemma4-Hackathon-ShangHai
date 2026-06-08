#include "plant_controller.h"
#include "display_ui.h"
#include "touch_feedback.h"

namespace {
const unsigned long SLEEP_TIMEOUT_MS = 10000;
const unsigned long SLEEP_PAGE_INTERVAL_MS = 6000;
const unsigned long SLEEP_FACE_FRAME_MS = 400;
const unsigned long BUBBLE_BASE_DURATION_MS = 3000;
const unsigned long BUBBLE_PER_WORD_MS = 400;
const unsigned long BUBBLE_MAX_DURATION_MS = 15000;
const int SLEEP_PAGE_COUNT = 3;

unsigned long calcBubbleDurationMs(const char* text) {
    if (text == nullptr || text[0] == '\0') return BUBBLE_BASE_DURATION_MS;
    int wordCount = 0;
    bool inWord = false;
    for (const char* p = text; *p; p++) {
        if (*p == ' ' || *p == '\n' || *p == '\t') {
            if (inWord) { wordCount++; inWord = false; }
        } else {
            inWord = true;
        }
    }
    if (inWord) wordCount++;
    unsigned long duration = BUBBLE_BASE_DURATION_MS + (unsigned long)wordCount * BUBBLE_PER_WORD_MS;
    if (duration > BUBBLE_MAX_DURATION_MS) duration = BUBBLE_MAX_DURATION_MS;
    return duration;
}
const int DEFAULT_MOISTURE_RAW = 800;
const int DEFAULT_TEMPERATURE_C = 28;

unsigned long lastInteractionTime = 0;
unsigned long lastSleepPageSwitchTime = 0;
unsigned long lastSleepRenderTime = 0;
unsigned long bubbleExpireTime = 0;

bool sleeping = true;
uint8_t sleepPage = 0;
uint8_t sleepAnimationFrame = 0;
int lastRenderedSleepMinute = -1;

int currentMoistureRaw = DEFAULT_MOISTURE_RAW;
int currentTemperatureC = DEFAULT_TEMPERATURE_C;
PlantEmotion currentEmotion = EMOTION_NORMAL;
PlantEmotion appEmotionOverride = EMOTION_NORMAL;
bool appEmotionOverrideActive = false;
const char* activeBubbleText = nullptr;
char bubbleBuffer[128] = {0};
char sleepQuoteBuffer[128] = {0};

PlantEmotion resolveDisplayEmotion() {
    return appEmotionOverrideActive ? appEmotionOverride : EMOTION_NORMAL;
}

void enterSleepMode() {
    sleeping = true;
    sleepPage = 0;
    lastSleepPageSwitchTime = millis();
    lastSleepRenderTime = 0;
    sleepAnimationFrame = 0;
    lastRenderedSleepMinute = -1;
    activeBubbleText = nullptr;
    bubbleExpireTime = 0;
    
    Serial.println("System Idle: Entering Sleep Mode");
    
    clearScreen();
    showSleepAnimationFrame(sleepAnimationFrame);
}

void updateSleepDisplay() {
    if (!sleeping) {
        return;
    }

    unsigned long now = millis();
    if (now - lastSleepPageSwitchTime >= SLEEP_PAGE_INTERVAL_MS) {
        lastSleepPageSwitchTime = now;
        lastSleepRenderTime = 0;
        lastRenderedSleepMinute = -1;
        sleepPage = (sleepPage + 1) % SLEEP_PAGE_COUNT;
        if (sleepPage == 2 && sleepQuoteBuffer[0] == '\0') {
            sleepPage = 0;
        }
        clearScreen();
    }

    if (sleepPage == 0) {
        if (lastSleepRenderTime == 0 || now - lastSleepRenderTime >= SLEEP_FACE_FRAME_MS) {
            lastSleepRenderTime = now;
            showSleepAnimationFrame(sleepAnimationFrame);
            sleepAnimationFrame = (sleepAnimationFrame + 1) % 4;
        }
    } else if (sleepPage == 1) {
        int currentMinute = (millis() / 60000UL) % 60;
        if (lastSleepRenderTime == 0 || currentMinute != lastRenderedSleepMinute) {
            lastSleepRenderTime = now;
            lastRenderedSleepMinute = currentMinute;
            showSleepClock();
        }
    } else if (sleepPage == 2) {
        if (lastSleepRenderTime == 0) {
            lastSleepRenderTime = now;
            showQuoteTextPage(sleepQuoteBuffer);
        }
    }
}
}  // namespace

void initPlantController() {
    lastInteractionTime = millis();
    resetEnvironmentToDefaults();
    currentEmotion = resolveDisplayEmotion();
    enterSleepMode();
}

void tickPlantController() {
    if (!sleeping && activeBubbleText != nullptr && millis() >= bubbleExpireTime) {
        activeBubbleText = nullptr;
        bubbleExpireTime = 0;
        renderAwakePlant();
    }

    updateSleepDisplay();

    // 如果当前处于对话模式，不进入休眠
    if (isTouchDialogModeActive()) {
        noteInteraction();
    }

    if (!sleeping && (millis() - lastInteractionTime > SLEEP_TIMEOUT_MS)) {
        enterSleepMode();
    }
}

bool isPlantSleeping() {
    return sleeping;
}

void wakePlant(const char* bubbleText) {
    if (!sleeping) {
        if (bubbleText != nullptr) {
            showBubble(bubbleText);
        }
        noteInteraction();
        return;
    }

    sleeping = false;
    sleepPage = 0;
    lastRenderedSleepMinute = -1;
    noteInteraction();

    if (bubbleText != nullptr) {
        strlcpy(sleepQuoteBuffer, bubbleText, sizeof(sleepQuoteBuffer));
    }

    showWakeUpAnimation(bubbleText);

    if (bubbleText != nullptr) {
        strlcpy(bubbleBuffer, bubbleText, sizeof(bubbleBuffer));
        activeBubbleText = bubbleBuffer;
        bubbleExpireTime = millis() + calcBubbleDurationMs(bubbleText);
    } else {
        activeBubbleText = nullptr;
        bubbleExpireTime = 0;
    }

    Serial.println("System Awake: Leaving Sleep Mode");
}

void noteInteraction() {
    lastInteractionTime = millis();
}

void resetEnvironmentToDefaults() {
    currentMoistureRaw = DEFAULT_MOISTURE_RAW;
    currentTemperatureC = DEFAULT_TEMPERATURE_C;
    currentEmotion = resolveDisplayEmotion();
}

void setAppEnvironment(int temperatureC, int moistureRaw) {
    currentTemperatureC = temperatureC;
    currentMoistureRaw = moistureRaw;
    currentEmotion = resolveDisplayEmotion();
    if (!sleeping) {
        renderAwakePlant();
    }
}

void setMoistureRaw(int moistureRaw) {
    currentMoistureRaw = moistureRaw;
    currentEmotion = resolveDisplayEmotion();
    setDisplaySensorData(currentMoistureRaw, currentTemperatureC);
}

void setTemperatureC(int temperatureC) {
    currentTemperatureC = temperatureC;
    currentEmotion = resolveDisplayEmotion();
    setDisplaySensorData(currentMoistureRaw, currentTemperatureC);
}

int getMoistureRaw() {
    return currentMoistureRaw;
}

int getTemperatureC() {
    return currentTemperatureC;
}

PlantEmotion getCurrentEmotion() {
    return currentEmotion;
}

void setAppEmotionOverride(PlantEmotion emotion) {
    appEmotionOverride = emotion;
    appEmotionOverrideActive = true;
    currentEmotion = resolveDisplayEmotion();
    if (!sleeping) {
        renderAwakePlant();
    }
}

void clearAppEmotionOverride() {
    appEmotionOverrideActive = false;
    currentEmotion = resolveDisplayEmotion();
    if (!sleeping) {
        renderAwakePlant();
    }
}

bool hasAppEmotionOverride() {
    return appEmotionOverrideActive;
}

void showBubble(const char* text) {
    if (text == nullptr) {
        return;
    }

    strlcpy(bubbleBuffer, text, sizeof(bubbleBuffer));
    activeBubbleText = bubbleBuffer;
    bubbleExpireTime = millis() + calcBubbleDurationMs(text);
    renderAwakePlant(activeBubbleText);
    Serial.print("Bubble: ");
    Serial.println(text);
}

void clearBubble() {
    activeBubbleText = nullptr;
    bubbleExpireTime = 0;
}

void renderAwakePlant(const char* bubbleText) {
    const char* textToShow = bubbleText != nullptr ? bubbleText : activeBubbleText;
    currentEmotion = resolveDisplayEmotion();
    showEmotionScreen(currentEmotion, currentMoistureRaw, currentTemperatureC, textToShow);
}
