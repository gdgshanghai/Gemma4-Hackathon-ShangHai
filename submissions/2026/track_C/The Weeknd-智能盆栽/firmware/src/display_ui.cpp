#include "display_ui.h"
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include "wifi_time.h"

#define TFT_CS    9
#define TFT_DC    10
#define TFT_RST   -1
#define TFT_MOSI  11
#define TFT_SCLK  12

#define ST7789_BLACK   0x0000
#define ST7789_WHITE   0xFFFF
#define ST7789_YELLOW  0xFFE0
#define ST7789_GREEN   0x04A0 // #4CAF50 approximate
#define ST7789_GRAY    0x8410 // #888 approximate
#define ST7789_SLEEP   0xAD55 // #aaa approximate
#define ST7789_BLUE    0x001F

Adafruit_ST7789 tft = Adafruit_ST7789(&SPI, TFT_CS, TFT_DC, TFT_RST);

// 映射 SVG 100x100 坐标到 320x240 屏幕 (放大 1.8 倍并居中)
#define MAP_X(x) (160 + ((x) - 50) * 1.8)
#define MAP_Y(y) (120 + ((y) - 50) * 1.8)

// 随机短按文案库
const char* touchTexts[] = {
    "I love being your plant!",
    "Thanks for the love!",
    "That feels nice!",
    "You're the best!",
    "Happy!"
};

int g_displayMoistureRaw = 2000;
int g_displayTemperature = 25;

void drawCenteredText(const char* text, int y, int size, uint16_t color);
void drawCenteredText(Adafruit_GFX* gfx, const char* text, int y, int size, uint16_t color);
void drawSleepFaceAtOffset(int faceOffsetY, int zOffsetX, int zOffsetY, int zTextSize);
void drawBreathingProgressBar(int progressWidth);
void clearSleepContentArea();
void drawBubbleText(const char* text);
void drawBubbleText(Adafruit_GFX* gfx, const char* text, int yOff = 0);
void drawEmotionFace(PlantEmotion emotion, uint16_t color);
void drawEmotionFace(Adafruit_GFX* gfx, PlantEmotion emotion, uint16_t color, int yOff = 0);
void drawUIBars(Adafruit_GFX* gfx);

static GFXcanvas16* s_sleepCanvas = nullptr;

static GFXcanvas16* getSleepCanvas() {
    if (s_sleepCanvas == nullptr) {
        s_sleepCanvas = new GFXcanvas16(320, 180);
        if (s_sleepCanvas && !s_sleepCanvas->getBuffer()) {
            delete s_sleepCanvas;
            s_sleepCanvas = nullptr;
        }
    }
    return s_sleepCanvas;
}

void freeSleepCanvas() {
    if (s_sleepCanvas) {
        delete s_sleepCanvas;
        s_sleepCanvas = nullptr;
    }
}

void drawThickQBezier(Adafruit_GFX* gfx, int x0, int y0, int cx, int cy, int x1, int y1, uint16_t color, int thickness) {
    float t;
    int last_x = x0, last_y = y0;
    for (t = 0.05; t <= 1.0; t += 0.05) {
        float inv = 1.0 - t;
        int x = inv*inv*x0 + 2*inv*t*cx + t*t*x1;
        int y = inv*inv*y0 + 2*inv*t*cy + t*t*y1;
        for(int i = -thickness/2; i <= thickness/2; i++) {
            for(int j = -thickness/2; j <= thickness/2; j++) {
                gfx->drawLine(last_x+i, last_y+j, x+i, y+j, color);
            }
        }
        last_x = x; last_y = y;
    }
}

void setDisplaySensorData(int moistureRaw, int temperatureC) {
    g_displayMoistureRaw = moistureRaw;
    g_displayTemperature = temperatureC;
}

void drawUIBars(Adafruit_GFX* gfx) {
    char timeText[6];
    getFormattedTime(timeText, sizeof(timeText));

    char tempText[16];
    snprintf(tempText, sizeof(tempText), "TEMP:%dC", g_displayTemperature);

    char moistureText[18];
    snprintf(moistureText, sizeof(moistureText), "RAW:%d", g_displayMoistureRaw);

    char ipText[20];
    getLocalIPStr(ipText, sizeof(ipText));

    gfx->setTextSize(1);
    gfx->setTextColor(ST7789_GRAY);
    gfx->setCursor(10, 10); gfx->print(timeText);
    gfx->setCursor(260, 10); gfx->print("BAT:100%");
    
    int16_t x1, y1;
    uint16_t w, h;
    gfx->getTextBounds(ipText, 0, 0, &x1, &y1, &w, &h);
    gfx->setCursor((320 - w) / 2, 10);
    gfx->print(ipText);

    gfx->setCursor(10, 220); gfx->print(tempText);
    gfx->setCursor(230, 220); gfx->print(moistureText);
}

void drawUIBars() {
    drawUIBars(&tft);
}

void initDisplay() {
    Serial.println("Display: Starting init...");
    SPI.begin(TFT_SCLK, -1, TFT_MOSI, TFT_CS);
    delay(200);
    tft.init(240, 320);
    tft.setSPISpeed(40000000);
    tft.setRotation(1); 
    tft.fillScreen(ST7789_BLACK);
    
    // GPIO4 现在给 DS18B20 使用，避免再对该引脚做模拟读取干扰单总线。
    randomSeed(micros());
    Serial.println("Display UI Initialized.");
}

void showBootScreen(const char* title, const char* subtitle) {
    tft.fillScreen(ST7789_BLUE);
    tft.drawRect(8, 8, 304, 224, ST7789_WHITE);
    tft.drawRect(12, 12, 296, 216, ST7789_WHITE);

    if (title != nullptr && title[0] != '\0') {
        drawCenteredText(title, 80, 3, ST7789_WHITE);
    }

    if (subtitle != nullptr && subtitle[0] != '\0') {
        drawCenteredText(subtitle, 135, 2, ST7789_WHITE);
    }

    tft.fillRect(60, 190, 200, 10, ST7789_WHITE);
    tft.fillRect(70, 194, 180, 2, ST7789_BLUE);
}

void drawBubbleText(Adafruit_GFX* gfx, const char* text, int yOff) {
    if (text == nullptr || text[0] == '\0') {
        return;
    }

    const int textSize = 2;
    const int maxBoxW = 280;
    const int padding = 12;
    const int lineHeight = 20;

    gfx->setTextSize(textSize);
    gfx->setTextColor(ST7789_BLACK);

    char lines[8][64];
    int lineCount = 0;
    int maxWidth = 0;

    const char* wordStart = text;
    char currentLine[64] = {0};

    while (*wordStart) {
        while (*wordStart == ' ') wordStart++;
        if (!*wordStart) break;

        const char* wordEnd = wordStart;
        while (*wordEnd && *wordEnd != ' ') wordEnd++;

        int wordLen = wordEnd - wordStart;
        char word[64];
        memcpy(word, wordStart, wordLen);
        word[wordLen] = '\0';

        char testLine[64];
        if (currentLine[0] == '\0') {
            strlcpy(testLine, word, sizeof(testLine));
        } else {
            snprintf(testLine, sizeof(testLine), "%s %s", currentLine, word);
        }

        int16_t x1, y1;
        uint16_t w, h;
        gfx->getTextBounds(testLine, 0, 0, &x1, &y1, &w, &h);

        if ((int)w > maxBoxW - padding * 2 && currentLine[0] != '\0') {
            if (lineCount < 8) {
                strlcpy(lines[lineCount], currentLine, 64);
                lineCount++;
                int16_t lx1, ly1;
                uint16_t lw, lh;
                gfx->getTextBounds(currentLine, 0, 0, &lx1, &ly1, &lw, &lh);
                if ((int)lw > maxWidth) maxWidth = lw;
            }
            strlcpy(currentLine, word, 64);
        } else {
            strlcpy(currentLine, testLine, 64);
        }

        wordStart = wordEnd;
    }

    if (currentLine[0] != '\0' && lineCount < 8) {
        strlcpy(lines[lineCount], currentLine, 64);
        lineCount++;
        int16_t lx1, ly1;
        uint16_t lw, lh;
        gfx->getTextBounds(currentLine, 0, 0, &lx1, &ly1, &lw, &lh);
        if ((int)lw > maxWidth) maxWidth = lw;
    }

    int boxW = maxWidth + padding * 2;
    if (boxW < 60) boxW = 60;
    if (boxW > maxBoxW) boxW = maxBoxW;
    int boxH = lineCount * lineHeight + padding * 2;
    int boxX = (320 - boxW) / 2;
    int boxY = 20 + yOff;

    gfx->fillRoundRect(boxX, boxY, boxW, boxH, 10, ST7789_WHITE);
    gfx->fillTriangle(150, boxY + boxH, 160, boxY + boxH + 10, 170, boxY + boxH, ST7789_WHITE);

    for (int i = 0; i < lineCount; i++) {
        gfx->setCursor(boxX + padding, boxY + padding + i * lineHeight);
        gfx->print(lines[i]);
    }
}

void drawBubbleText(const char* text) {
    drawBubbleText(&tft, text, 0);
}

void drawEmotionFace(Adafruit_GFX* gfx, PlantEmotion emotion, uint16_t color, int yOff) {
    switch (emotion) {
        case EMOTION_TOUCH:
            drawThickQBezier(gfx, MAP_X(25), MAP_Y(45)+yOff, MAP_X(35), MAP_Y(30)+yOff, MAP_X(45), MAP_Y(45)+yOff, color, 4);
            drawThickQBezier(gfx, MAP_X(55), MAP_Y(45)+yOff, MAP_X(65), MAP_Y(30)+yOff, MAP_X(75), MAP_Y(45)+yOff, color, 4);
            drawThickQBezier(gfx, MAP_X(30), MAP_Y(65)+yOff, MAP_X(50), MAP_Y(85)+yOff, MAP_X(70), MAP_Y(65)+yOff, color, 4);
            break;
        case EMOTION_THIRSTY:
            gfx->fillRoundRect(MAP_X(35)-6, MAP_Y(50)-4+yOff, 12, 8, 4, color);
            gfx->fillRoundRect(MAP_X(65)-6, MAP_Y(50)-4+yOff, 12, 8, 4, color);
            drawThickQBezier(gfx, MAP_X(35), MAP_Y(75)+yOff, MAP_X(50), MAP_Y(60)+yOff, MAP_X(65), MAP_Y(75)+yOff, color, 4);
            break;
        case EMOTION_DROWN:
            gfx->drawLine(MAP_X(25), MAP_Y(35)+yOff, MAP_X(45), MAP_Y(55)+yOff, color);
            gfx->drawLine(MAP_X(25), MAP_Y(55)+yOff, MAP_X(45), MAP_Y(35)+yOff, color);
            gfx->drawLine(MAP_X(55), MAP_Y(35)+yOff, MAP_X(75), MAP_Y(55)+yOff, color);
            gfx->drawLine(MAP_X(55), MAP_Y(55)+yOff, MAP_X(75), MAP_Y(35)+yOff, color);
            drawThickQBezier(gfx, MAP_X(30), MAP_Y(75)+yOff, MAP_X(40), MAP_Y(85)+yOff, MAP_X(50), MAP_Y(75)+yOff, color, 3);
            drawThickQBezier(gfx, MAP_X(50), MAP_Y(75)+yOff, MAP_X(60), MAP_Y(65)+yOff, MAP_X(70), MAP_Y(75)+yOff, color, 3);
            break;
        case EMOTION_HOT:
            gfx->fillRoundRect(MAP_X(35)-6, MAP_Y(50)-4+yOff, 12, 8, 4, color);
            gfx->fillRoundRect(MAP_X(65)-6, MAP_Y(50)-4+yOff, 12, 8, 4, color);
            drawThickQBezier(gfx, MAP_X(35), MAP_Y(75)+yOff, MAP_X(50), MAP_Y(60)+yOff, MAP_X(65), MAP_Y(75)+yOff, color, 4);
            break;
        case EMOTION_COLD:
            gfx->fillRoundRect(MAP_X(35)-6, MAP_Y(45)-8+yOff, 12, 16, 6, color);
            gfx->fillRoundRect(MAP_X(65)-6, MAP_Y(45)-8+yOff, 12, 16, 6, color);
            gfx->drawLine(MAP_X(30), MAP_Y(70)+yOff, MAP_X(40), MAP_Y(65)+yOff, color);
            gfx->drawLine(MAP_X(40), MAP_Y(65)+yOff, MAP_X(50), MAP_Y(70)+yOff, color);
            gfx->drawLine(MAP_X(50), MAP_Y(70)+yOff, MAP_X(60), MAP_Y(65)+yOff, color);
            gfx->drawLine(MAP_X(60), MAP_Y(65)+yOff, MAP_X(70), MAP_Y(70)+yOff, color);
            break;
        case EMOTION_DEADLY:
            gfx->drawLine(MAP_X(25), MAP_Y(35)+yOff, MAP_X(45), MAP_Y(55)+yOff, color);
            gfx->drawLine(MAP_X(25), MAP_Y(55)+yOff, MAP_X(45), MAP_Y(35)+yOff, color);
            gfx->drawLine(MAP_X(55), MAP_Y(35)+yOff, MAP_X(75), MAP_Y(55)+yOff, color);
            gfx->drawLine(MAP_X(55), MAP_Y(55)+yOff, MAP_X(75), MAP_Y(35)+yOff, color);
            gfx->fillRect(MAP_X(30), MAP_Y(75)+yOff, MAP_X(70) - MAP_X(30), 4, color);
            break;
        case EMOTION_NORMAL:
        default:
            gfx->fillRoundRect(MAP_X(35)-6, MAP_Y(45)-8+yOff, 12, 16, 6, color);
            gfx->fillRoundRect(MAP_X(65)-6, MAP_Y(45)-8+yOff, 12, 16, 6, color);
            drawThickQBezier(gfx, MAP_X(30), MAP_Y(65)+yOff, MAP_X(50), MAP_Y(85)+yOff, MAP_X(70), MAP_Y(65)+yOff, color, 4);
            break;
    }
}

void drawEmotionFace(PlantEmotion emotion, uint16_t color) {
    drawEmotionFace(&tft, emotion, color, 0);
}

void showEmotionScreen(PlantEmotion emotion, int moistureRaw, int temperatureC, const char* bubbleText) {
    g_displayMoistureRaw = moistureRaw;
    g_displayTemperature = temperatureC;

    uint16_t color = ST7789_WHITE;
    if (emotion == EMOTION_THIRSTY) color = ST7789_YELLOW;
    if (emotion == EMOTION_DROWN) color = 0x05DF;
    if (emotion == EMOTION_HOT) color = 0xFA20;
    if (emotion == EMOTION_COLD) color = 0xAF7D;
    if (emotion == EMOTION_DEADLY) color = 0xF800;

    GFXcanvas16* canvas = new GFXcanvas16(320, 180);
    if (canvas && canvas->getBuffer()) {
        tft.fillRect(0, 0, 320, 20, ST7789_BLACK);
        tft.fillRect(0, 200, 320, 40, ST7789_BLACK);
        drawUIBars(&tft);
        canvas->fillScreen(ST7789_BLACK);
        drawBubbleText(canvas, bubbleText, -20);
        drawEmotionFace(canvas, emotion, color, -20);
        tft.drawRGBBitmap(0, 20, canvas->getBuffer(), 320, 180);
        delete canvas;
    } else {
        if (canvas) { delete canvas; canvas = nullptr; }
        tft.fillScreen(ST7789_BLACK);
        drawUIBars();
        drawBubbleText(bubbleText);
        drawEmotionFace(emotion, color);
    }
}

void showNormalFace() {
    showEmotionScreen(EMOTION_NORMAL, g_displayMoistureRaw, g_displayTemperature);
    Serial.println("Display: Normal Face");
}

void showDialogAnimationFrame(uint8_t frame) {
    uint16_t color = ST7789_WHITE;
    const int yOffsets[] = {0, -3, -6, -3};
    int offsetY = yOffsets[frame % 4];
    static GFXcanvas16* dialogCanvas = nullptr;

    if (dialogCanvas == nullptr) {
        dialogCanvas = new GFXcanvas16(320, 180);
    }

    if (dialogCanvas == nullptr) {
        tft.fillRect(0, 20, 320, 180, ST7789_BLACK);
        drawThickQBezier(&tft, MAP_X(25), MAP_Y(45) + offsetY, MAP_X(35), MAP_Y(30) + offsetY, MAP_X(45), MAP_Y(45) + offsetY, color, 4);
        drawThickQBezier(&tft, MAP_X(55), MAP_Y(45) + offsetY, MAP_X(65), MAP_Y(30) + offsetY, MAP_X(75), MAP_Y(45) + offsetY, color, 4);
        drawThickQBezier(&tft, MAP_X(30), MAP_Y(65) + offsetY, MAP_X(50), MAP_Y(85) + offsetY, MAP_X(70), MAP_Y(65) + offsetY, color, 4);
        return;
    }

    dialogCanvas->fillScreen(ST7789_BLACK);
    int yAdjust = -20;
    drawThickQBezier(dialogCanvas, MAP_X(25), MAP_Y(45) + offsetY + yAdjust, MAP_X(35), MAP_Y(30) + offsetY + yAdjust, MAP_X(45), MAP_Y(45) + offsetY + yAdjust, color, 4);
    drawThickQBezier(dialogCanvas, MAP_X(55), MAP_Y(45) + offsetY + yAdjust, MAP_X(65), MAP_Y(30) + offsetY + yAdjust, MAP_X(75), MAP_Y(45) + offsetY + yAdjust, color, 4);
    drawThickQBezier(dialogCanvas, MAP_X(30), MAP_Y(65) + offsetY + yAdjust, MAP_X(50), MAP_Y(85) + offsetY + yAdjust, MAP_X(70), MAP_Y(65) + offsetY + yAdjust, color, 4);
    tft.drawRGBBitmap(0, 20, dialogCanvas->getBuffer(), 320, 180);
}

void clearSleepContentArea() {
    tft.fillScreen(ST7789_BLACK);
}

void drawSleepFaceAtOffset(int faceOffsetY, int zOffsetX, int zOffsetY, int zTextSize) {
    GFXcanvas16* canvas = getSleepCanvas();
    Adafruit_GFX* gfx = canvas ? (Adafruit_GFX*)canvas : (Adafruit_GFX*)&tft;
    const int yAdj = canvas ? -20 : 0;

    gfx->fillScreen(ST7789_BLACK);
    uint16_t color = ST7789_SLEEP;
    
    drawThickQBezier(gfx, MAP_X(25), MAP_Y(45) + faceOffsetY + yAdj, MAP_X(35), MAP_Y(55) + faceOffsetY + yAdj, MAP_X(45), MAP_Y(45) + faceOffsetY + yAdj, color, 4);
    drawThickQBezier(gfx, MAP_X(55), MAP_Y(45) + faceOffsetY + yAdj, MAP_X(65), MAP_Y(55) + faceOffsetY + yAdj, MAP_X(75), MAP_Y(45) + faceOffsetY + yAdj, color, 4);
    
    gfx->setTextSize(zTextSize);
    gfx->setTextColor(color);
    gfx->setCursor(MAP_X(95) + zOffsetX, MAP_Y(10) + zOffsetY + yAdj);
    gfx->print("Z");

    if (zTextSize >= 3) {
        gfx->setTextSize(zTextSize - 1);
        gfx->setCursor(MAP_X(85) + zOffsetX / 2, MAP_Y(18) + zOffsetY / 2 + yAdj);
        gfx->print("z");
    }

    if (canvas) tft.drawRGBBitmap(0, 20, canvas->getBuffer(), 320, 180);
}

void showSleepFace() {
    drawSleepFaceAtOffset(0, 0, 0, 4);
    Serial.println("Display: Sleep Face");
}

void showSleepAnimationFrame(uint8_t frame) {
    const int faceOffsets[] = {0, -2, -3, -2};
    const int zOffsetX[] = {0, 4, 8, 12};
    const int zOffsetY[] = {0, -4, -8, -12};
    const int zTextSizes[] = {4, 4, 3, 3};

    uint8_t index = frame % 4;
    drawSleepFaceAtOffset(faceOffsets[index], zOffsetX[index], zOffsetY[index], zTextSizes[index]);
    Serial.println("Display: Sleep Animation Frame");
}

void showSleepClock() {
    GFXcanvas16* canvas = getSleepCanvas();
    Adafruit_GFX* gfx = canvas ? (Adafruit_GFX*)canvas : (Adafruit_GFX*)&tft;

    gfx->fillScreen(ST7789_BLACK);

    char timeText[6];
    getFormattedTime(timeText, sizeof(timeText));

    drawCenteredText(gfx, timeText, canvas ? 75 : 95, 5, ST7789_SLEEP);

    if (canvas) tft.drawRGBBitmap(0, 20, canvas->getBuffer(), 320, 180);
    Serial.println("Display: Sleep Clock");
}

void showQuoteTextPage(const char* text) {
    if (text == nullptr || text[0] == '\0') {
        showSleepClock();
        return;
    }

    GFXcanvas16* canvas = getSleepCanvas();
    Adafruit_GFX* gfx = canvas ? (Adafruit_GFX*)canvas : (Adafruit_GFX*)&tft;

    gfx->fillScreen(ST7789_BLACK);

    const int textSize = 2;
    const int maxW = 300;
    const int lineH = 20;
    const int padY = 30;

    gfx->setTextSize(textSize);
    gfx->setTextColor(ST7789_WHITE);

    char lines[10][64];
    int lineCount = 0;
    char word[64];
    char curLine[64] = "";
    const char* p = text;

    while (*p && lineCount < 10) {
        while (*p == ' ') p++;
        if (!*p) break;

        int i = 0;
        while (*p && *p != ' ' && i < 63) {
            word[i++] = *p++;
        }
        word[i] = '\0';

        char testLine[128];
        if (curLine[0] == '\0') {
            snprintf(testLine, sizeof(testLine), "%s", word);
        } else {
            snprintf(testLine, sizeof(testLine), "%s %s", curLine, word);
        }

        int16_t x1, y1;
        uint16_t w, h;
        gfx->getTextBounds(testLine, 0, 0, &x1, &y1, &w, &h);

        if (w > maxW && curLine[0] != '\0') {
            strlcpy(lines[lineCount], curLine, 64);
            lineCount++;
            strlcpy(curLine, word, 64);
        } else {
            strlcpy(curLine, testLine, 64);
        }
    }

    if (curLine[0] != '\0' && lineCount < 10) {
        strlcpy(lines[lineCount], curLine, 64);
        lineCount++;
    }

    int totalH = lineCount * lineH;
    int charAscent = textSize * 8;
    int startY = canvas ? ((180 - totalH) / 2 + charAscent) : ((240 - totalH) / 2 + charAscent);
    if (startY < (canvas ? 10 : padY)) startY = (canvas ? 10 : padY);

    for (int i = 0; i < lineCount; i++) {
        int16_t x1, y1;
        uint16_t w, h;
        gfx->getTextBounds(lines[i], 0, 0, &x1, &y1, &w, &h);
        int x = (320 - w) / 2;
        int y = startY + i * lineH;
        gfx->setCursor(x, y);
        gfx->print(lines[i]);
    }

    if (canvas) tft.drawRGBBitmap(0, 20, canvas->getBuffer(), 320, 180);

    Serial.print("Display: Quote Text - ");
    Serial.println(text);
}

void drawVoiceBubble(Adafruit_GFX* gfx, int y, const char* text) {
    int16_t x1, y1; uint16_t w, h;
    gfx->setTextSize(2);
    gfx->getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
    
    int boxW = w + 20;
    int boxH = 40;
    int boxX = 160 - boxW/2;
    
    gfx->fillRoundRect(boxX, y, boxW, boxH, 10, ST7789_WHITE);
    gfx->fillTriangle(160 - 10, y + boxH, 160, y + boxH + 10, 160 + 10, y + boxH, ST7789_WHITE);
    gfx->setTextColor(ST7789_BLACK);
    gfx->setCursor(boxX + 10, y + 12);
    gfx->print(text);
}

void showWakeUpAnimation(const char* bubbleText) {
    freeSleepCanvas();

    const int frameDelay = 120;
    const uint16_t awakeColor = ST7789_WHITE;
    const uint16_t sleepColor = ST7789_SLEEP;

    GFXcanvas16* canvas = new GFXcanvas16(320, 180);
    Adafruit_GFX* gfx = canvas ? (Adafruit_GFX*)canvas : (Adafruit_GFX*)&tft;
    const int yAdj = canvas ? -20 : 0;

    tft.fillScreen(ST7789_BLACK);
    drawUIBars();

    const int closedCtrlY[] = {55, 50, 43, 35, 30};
    const uint16_t frameColors[] = {sleepColor, sleepColor, awakeColor, awakeColor, awakeColor};

    for (int f = 0; f < 5; f++) {
        if (canvas) canvas->fillScreen(ST7789_BLACK);
        else gfx->fillRect(0, 20, 320, 180, ST7789_BLACK);

        int ctrlY = closedCtrlY[f];
        drawThickQBezier(gfx, MAP_X(25), MAP_Y(45)+yAdj, MAP_X(35), MAP_Y(ctrlY)+yAdj, MAP_X(45), MAP_Y(45)+yAdj, frameColors[f], 4);
        drawThickQBezier(gfx, MAP_X(55), MAP_Y(45)+yAdj, MAP_X(65), MAP_Y(ctrlY)+yAdj, MAP_X(75), MAP_Y(45)+yAdj, frameColors[f], 4);
        drawThickQBezier(gfx, MAP_X(30), MAP_Y(65)+yAdj, MAP_X(50), MAP_Y(85)+yAdj, MAP_X(70), MAP_Y(65)+yAdj, frameColors[f], 4);

        if (canvas) tft.drawRGBBitmap(0, 20, canvas->getBuffer(), 320, 180);
        delay(frameDelay);
    }

    if (canvas) delete canvas;

    showEmotionScreen(EMOTION_NORMAL, g_displayMoistureRaw, g_displayTemperature, bubbleText);
}

void triggerShortPressAction() {
    uint16_t color = ST7789_WHITE;
    const char* text = touchTexts[random(0, 5)];
    
    // 使用双缓冲 Canvas 解决频闪问题，只刷新中间动画区域
    GFXcanvas16* canvas = new GFXcanvas16(320, 180);
    Adafruit_GFX* gfx = canvas ? (Adafruit_GFX*)canvas : (Adafruit_GFX*)&tft;
    
    tft.fillScreen(ST7789_BLACK);
    drawUIBars();

    for (int i = 0; i < 2; i++) {
        // 向上浮动
        for (int off = 0; off >= -15; off -= 2) {
            if (canvas) canvas->fillScreen(ST7789_BLACK);
            else tft.fillRect(0, 20, 320, 180, ST7789_BLACK);
            
            int y_adj = canvas ? -20 : 0;
            drawThickQBezier(gfx, MAP_X(25), MAP_Y(45)+off+y_adj, MAP_X(35), MAP_Y(30)+off+y_adj, MAP_X(45), MAP_Y(45)+off+y_adj, color, 4);
            drawThickQBezier(gfx, MAP_X(55), MAP_Y(45)+off+y_adj, MAP_X(65), MAP_Y(30)+off+y_adj, MAP_X(75), MAP_Y(45)+off+y_adj, color, 4);
            drawThickQBezier(gfx, MAP_X(30), MAP_Y(65)+off+y_adj, MAP_X(50), MAP_Y(85)+off+y_adj, MAP_X(70), MAP_Y(65)+off+y_adj, color, 4);
            drawVoiceBubble(gfx, 40 + off + y_adj, text);
            
            if (canvas) tft.drawRGBBitmap(0, 20, canvas->getBuffer(), 320, 180);
            delay(15);
        }
        delay(300);

        // 向下浮动
        for (int off = -15; off <= 0; off += 2) {
            if (canvas) canvas->fillScreen(ST7789_BLACK);
            else tft.fillRect(0, 20, 320, 180, ST7789_BLACK);
            
            int y_adj = canvas ? -20 : 0;
            drawThickQBezier(gfx, MAP_X(25), MAP_Y(45)+off+y_adj, MAP_X(35), MAP_Y(30)+off+y_adj, MAP_X(45), MAP_Y(45)+off+y_adj, color, 4);
            drawThickQBezier(gfx, MAP_X(55), MAP_Y(45)+off+y_adj, MAP_X(65), MAP_Y(30)+off+y_adj, MAP_X(75), MAP_Y(45)+off+y_adj, color, 4);
            drawThickQBezier(gfx, MAP_X(30), MAP_Y(65)+off+y_adj, MAP_X(50), MAP_Y(85)+off+y_adj, MAP_X(70), MAP_Y(65)+off+y_adj, color, 4);
            drawVoiceBubble(gfx, 40 + off + y_adj, text);
            
            if (canvas) tft.drawRGBBitmap(0, 20, canvas->getBuffer(), 320, 180);
            delay(15);
        }
        delay(300);
    }
    if (canvas) delete canvas;
    delay(1000);
}

void drawCenteredText(Adafruit_GFX* gfx, const char* text, int y, int size, uint16_t color) {
    gfx->setTextSize(size);
    gfx->setTextColor(color);
    int16_t x1, y1; uint16_t w, h;
    gfx->getTextBounds(text, 0, y, &x1, &y1, &w, &h);
    gfx->setCursor((320 - w) / 2, y);
    gfx->print(text);
}

void drawCenteredText(const char* text, int y, int size, uint16_t color) {
    drawCenteredText(&tft, text, y, size, color);
}

void drawBreathingProgressBar(int progressWidth) {
    if (progressWidth < 0) progressWidth = 0;
    if (progressWidth > 160) progressWidth = 160;

    tft.drawRect(79, 209, 162, 12, ST7789_WHITE);
    tft.fillRect(80, 210, 160, 10, ST7789_BLACK);
    if (progressWidth > 0) {
        tft.fillRect(80, 210, progressWidth, 10, ST7789_GREEN);
    }
}

void drawLeaf(Adafruit_GFX* gfx, int cx, int cy, int radius) {
    gfx->fillCircle(cx, cy + radius/2, radius, ST7789_GREEN);
    gfx->fillTriangle(cx - radius, cy + radius/2, cx + radius, cy + radius/2, cx, cy - radius*1.5, ST7789_GREEN);
}

void runBreathingTraining(int touchPin) {
    const int inhaleSteps = 30;
    const int exhaleSteps = 40;
    const int cycleCount = 6;
    const int cycleFrames = inhaleSteps + exhaleSteps + 2;
    const int totalFrames = cycleCount * cycleFrames;
    
    tft.fillScreen(ST7789_BLACK);
    
    const char* countdown[] = {"Take a breath", "Ready?", "3", "2", "1"};
    for (int i = 0; i < 5; i++) {
        tft.fillRect(0, 100, 320, 40, ST7789_BLACK);
        drawCenteredText(countdown[i], 110, i >= 2 ? 5 : 3, ST7789_WHITE);
        for (int t = 0; t < 100; t++) { 
            delay(10);
        }
    }

    GFXcanvas16* canvas = new GFXcanvas16(160, 160);
    tft.fillScreen(ST7789_BLACK);
    
    for (int cycle = 0; cycle < cycleCount; cycle++) {
        tft.fillRect(0, 10, 320, 30, ST7789_BLACK);
        drawCenteredText("Inhale...", 10, 3, ST7789_GREEN);
        drawBreathingProgressBar((cycle * 160) / cycleCount);
        
        for (int step = 0; step <= inhaleSteps; step++) {
            int frameIndex = cycle * cycleFrames + step;
            int prog = map(frameIndex, 0, totalFrames - 1, 0, 160);
            drawBreathingProgressBar(prog);
            
            int radius = 15 + step; 
            if (canvas) {
                canvas->fillScreen(ST7789_BLACK);
                drawLeaf(canvas, 80, 80, radius);
                tft.drawRGBBitmap(80, 40, canvas->getBuffer(), 160, 160);
            } else {
                tft.fillRect(80, 40, 160, 160, ST7789_BLACK); 
                drawLeaf(&tft, 160, 120, radius);
            }
            delay(40); 
        }
        
        tft.fillRect(0, 10, 320, 30, ST7789_BLACK);
        drawCenteredText("Exhale...", 10, 3, ST7789_GREEN);
        
        for (int step = 0; step <= exhaleSteps; step++) {
            int frameIndex = cycle * cycleFrames + (inhaleSteps + 1) + step;
            int prog = map(frameIndex, 0, totalFrames - 1, 0, 160);
            drawBreathingProgressBar(prog);
            
            int radius = 45 - (step * 30 / exhaleSteps); 
            if (canvas) {
                canvas->fillScreen(ST7789_BLACK);
                drawLeaf(canvas, 80, 80, radius);
                tft.drawRGBBitmap(80, 40, canvas->getBuffer(), 160, 160);
            } else {
                tft.fillRect(80, 40, 160, 160, ST7789_BLACK); 
                drawLeaf(&tft, 160, 120, radius);
            }
            delay(40); 
        }
    }
    
    if (canvas) delete canvas;
    tft.fillScreen(ST7789_BLACK);
    drawBreathingProgressBar(160);
    drawCenteredText("Well done!", 110, 3, ST7789_GREEN);
    for (int t = 0; t < 200; t++) { 
        delay(10);
    }
    
    showNormalFace();
}

void clearScreen() {
    tft.fillScreen(ST7789_BLACK);
}
