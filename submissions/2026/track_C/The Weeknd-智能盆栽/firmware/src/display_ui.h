#ifndef DISPLAY_UI_H
#define DISPLAY_UI_H

#include <Arduino.h>

enum PlantEmotion : uint8_t {
    EMOTION_NORMAL = 0,
    EMOTION_TOUCH,
    EMOTION_THIRSTY,
    EMOTION_DROWN,
    EMOTION_HOT,
    EMOTION_COLD,
    EMOTION_DEADLY
};

// 初始化显示模块
void initDisplay();

// 按当前情绪与传感器值渲染主界面
void showEmotionScreen(PlantEmotion emotion, int moistureRaw, int temperatureC, const char* bubbleText = nullptr);

// 显示没有表情的脸 (常驻状态)
void showNormalFace();

// 显示一帧对话模式动画
void showDialogAnimationFrame(uint8_t frame);

// 显示休眠表情
void showSleepFace();

// 显示一帧休眠动画
void showSleepAnimationFrame(uint8_t frame);

// 显示休眠时钟画面
void showSleepClock();

// 显示休眠语录页面（全屏大字）
void showQuoteTextPage(const char* text);

// 触发唤醒动画（睁眼 + 气泡文字）
void showWakeUpAnimation(const char* bubbleText = nullptr);

// 触发短按动画（上下浮动 + 语音气泡）
void triggerShortPressAction();

// 触发长按动画（呼吸训练）
void runBreathingTraining(int touchPin);

// 显示启动自检/阶段画面
void showBootScreen(const char* title, const char* subtitle = nullptr);

// 清屏
void clearScreen();

// 释放休眠Canvas内存
void freeSleepCanvas();

// 绘制顶部/底部UI信息栏（时间、温度、湿度、IP、电量）
void drawUIBars();

// 同步传感器数据到显示层
void setDisplaySensorData(int moistureRaw, int temperatureC);

#endif
