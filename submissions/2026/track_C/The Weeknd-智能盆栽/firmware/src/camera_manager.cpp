#include "camera_manager.h"
#include "hardware_config.h"

bool initCamera() {
    Serial.println("Camera: Initializing...");
    camera_config_t config;
    memset(&config, 0, sizeof(config)); 
    
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = CAM_PIN_D0;
    config.pin_d1 = CAM_PIN_D1;
    config.pin_d2 = CAM_PIN_D2;
    config.pin_d3 = CAM_PIN_D3;
    config.pin_d4 = CAM_PIN_D4;
    config.pin_d5 = CAM_PIN_D5;
    config.pin_d6 = CAM_PIN_D6;
    config.pin_d7 = CAM_PIN_D7;
    config.pin_xclk = CAM_PIN_XCLK;
    config.pin_pclk = CAM_PIN_PCLK;
    config.pin_vsync = CAM_PIN_VSYNC;
    config.pin_href = CAM_PIN_HREF;
    config.pin_sccb_sda = CAM_PIN_SIOD;
    config.pin_sccb_scl = CAM_PIN_SIOC;
    config.pin_pwdn = CAM_PIN_PWDN;
    config.pin_reset = CAM_PIN_RESET;
    config.xclk_freq_hz = 10000000; // 降低到 10MHz 尝试提高兼容性
    config.frame_size = FRAMESIZE_QVGA; // 先用低分辨率测试
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.jpeg_quality = 12;
    config.fb_count = 1;

    Serial.println("Camera: Calling esp_camera_init...");
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed with error 0x%x\n", err);
        return false;
    }

    sensor_t * s = esp_camera_sensor_get();
    if (s) {
        Serial.printf("Camera: Sensor PID=0x%x\n", s->id.PID);
        if (s->id.PID == GC0308_PID) {
            Serial.println("Camera: GC0308 detected");
        }
        // 尝试翻转图像，如果画面是反的
        s->set_vflip(s, 1);
        s->set_hmirror(s, 1);
    }

    Serial.println("Camera: Initialized successfully");
    return true;
}

camera_fb_t* captureFrame() {
    return esp_camera_fb_get();
}

void releaseFrame(camera_fb_t* fb) {
    esp_camera_fb_return(fb);
}
