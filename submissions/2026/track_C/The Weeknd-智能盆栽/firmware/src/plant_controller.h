#ifndef PLANT_CONTROLLER_H
#define PLANT_CONTROLLER_H

#include <Arduino.h>
#include "display_ui.h"

void initPlantController();
void tickPlantController();

bool isPlantSleeping();
void wakePlant(const char* bubbleText = nullptr);
void noteInteraction();

void resetEnvironmentToDefaults();
void setAppEnvironment(int temperatureC, int moistureRaw);
void setMoistureRaw(int moistureRaw);
void setTemperatureC(int temperatureC);
int getMoistureRaw();
int getTemperatureC();
PlantEmotion getCurrentEmotion();
void setAppEmotionOverride(PlantEmotion emotion);
void clearAppEmotionOverride();
bool hasAppEmotionOverride();

void showBubble(const char* text);
void clearBubble();
void renderAwakePlant(const char* bubbleText = nullptr);

#endif
