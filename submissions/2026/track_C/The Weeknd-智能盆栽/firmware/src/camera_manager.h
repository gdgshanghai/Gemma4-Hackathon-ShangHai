#ifndef CAMERA_MANAGER_H
#define CAMERA_MANAGER_H

#include <Arduino.h>
#include "esp_camera.h"

// 初始化摄像头
bool initCamera();

// 获取当前帧数据
camera_fb_t* captureFrame();

// 释放帧数据
void releaseFrame(camera_fb_t* fb);

#endif
