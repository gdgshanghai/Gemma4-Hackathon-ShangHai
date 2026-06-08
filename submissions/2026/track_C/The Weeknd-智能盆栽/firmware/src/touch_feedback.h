#ifndef TOUCH_FEEDBACK_H
#define TOUCH_FEEDBACK_H

#include <Arduino.h>

// 初始化触摸反馈功能
void initTouchFeedback();

// 处理触摸反馈逻辑（需在 loop 中调用）
void handleTouchFeedback();

// 获取对话模式是否激活
bool isTouchDialogModeActive();

#endif
