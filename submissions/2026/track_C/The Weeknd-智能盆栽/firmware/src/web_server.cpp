#include "web_server.h"
#include <WiFi.h>
#include <WebServer.h>
#include "plant_controller.h"
#include "camera_manager.h"
#include <ArduinoJson.h>

namespace {
WebServer server(80);

void handleRoot() {
    String html = "<html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'><title>智能花盆状态</title>";
    html += "<style>body{font-family:-apple-system,sans-serif;text-align:center;padding:20px;background-color:#f4f7f6;}";
    html += ".card{background:white;display:inline-block;padding:20px;border-radius:15px;box-shadow:0 4px 15px rgba(0,0,0,0.1);max-width:400px;width:100%;}";
    html += "h1{color:#2ecc71;margin-bottom:20px;}";
    html += ".data-item{margin:10px 0;font-size:1.1em;color:#34495e;}";
    html += ".label{font-weight:bold;color:#7f8c8d;font-size:0.8em;display:block;}";
    html += ".value{font-size:1.2em;color:#2c3e50;}";
    html += ".cam-img{width:100%;border-radius:10px;margin-bottom:15px;background:#eee;aspect-ratio:4/3;object-fit:cover;}";
    html += ".cam-fallback{display:none;border-radius:10px;margin-bottom:15px;padding:24px;background:#eef7f1;color:#2c3e50;}</style></head><body>";
    html += "<div class='card'><h1>智能花盆状态</h1>";
    
    html += "<img src='/camera' class='cam-img' onerror=\"this.style.display='none';document.getElementById('cam-fallback').style.display='block';\">";
    html += "<div id='cam-fallback' class='cam-fallback'>摄像头暂未就绪，请检查模块连接或稍后刷新页面。</div>";

    html += "<div class='data-item'><span class='label'>温度</span><span class='value'>" + String(getTemperatureC()) + " ℃</span></div>";
    html += "<div class='data-item'><span class='label'>土壤湿度 (RAW)</span><span class='value'>" + String(getMoistureRaw()) + "</span></div>";
    html += "<div class='data-item'><span class='label'>当前情绪</span><span class='value'>" + String((int)getCurrentEmotion()) + "</span></div>";
    html += "<div class='data-item'><span class='label'>休眠状态</span><span class='value'>" + String(isPlantSleeping() ? "休眠中" : "清醒") + "</span></div>";
    
    html += "<hr style='border:0;border-top:1px solid #eee;margin:20px 0;'>";
    html += "<button onclick='location.reload()' style='padding:10px 20px;border-radius:5px;border:none;background:#2ecc71;color:white;cursor:pointer;'>刷新画面</button>";
    html += "</div></body></html>";
    server.send(200, "text/html", html);
}

void handleCamera() {
    camera_fb_t * fb = captureFrame();
    if (!fb) {
        server.send(500, "text/plain", "Camera capture failed");
        return;
    }
    
    server.sendHeader("Content-Type", "image/jpeg");
    server.sendHeader("Content-Length", String(fb->len));
    server.sendHeader("Access-Control-Allow-Origin", "*");
    
    WiFiClient client = server.client();
    client.write(fb->buf, fb->len);
    
    releaseFrame(fb);
}

void handleApiData() {
    Serial.println("HTTP GET /api/data");
    JsonDocument doc;
    doc["temperature"] = getTemperatureC();
    doc["moisture"] = getMoistureRaw();
    doc["emotion"] = (int)getCurrentEmotion();
    doc["is_sleeping"] = isPlantSleeping();
    doc["has_override"] = hasAppEmotionOverride();
    doc["ip"] = WiFi.localIP().toString();

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void handleSetEmotion() {
    if (server.hasArg("id")) {
        int emotionId = server.arg("id").toInt();
        setAppEmotionOverride((PlantEmotion)emotionId);
        server.send(200, "application/json", "{\"status\":\"ok\"}");
    } else {
        server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"missing id\"}");
    }
}

void handleClearEmotion() {
    clearAppEmotionOverride();
    server.send(200, "application/json", "{\"status\":\"ok\"}");
}

void handleWake() {
    wakePlant("你好，主人~");
    server.send(200, "application/json", "{\"status\":\"ok\"}");
}

void handleQuote() {
    if (server.hasArg("text")) {
        String quote = server.arg("text");
        wakePlant(quote.c_str());
        server.send(200, "application/json", "{\"status\":\"ok\"}");
    } else {
        server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"missing text\"}");
    }
}

void handlePing() {
    server.send(200, "application/json", "{\"status\":\"pong\"}");
}

} // namespace

void initWebServer() {
    server.on("/", handleRoot);
    server.on("/camera", HTTP_GET, handleCamera);
    server.on("/api/data", HTTP_GET, handleApiData);
    server.on("/api/set_emotion", HTTP_GET, handleSetEmotion);
    server.on("/api/clear_emotion", HTTP_GET, handleClearEmotion);
    server.on("/api/wake", HTTP_GET, handleWake);
    server.on("/api/quote", HTTP_GET, handleQuote);
    server.on("/api/ping", HTTP_GET, handlePing);
    
    server.begin();
    Serial.println("HTTP Server: Started on port 80");
}

void handleWebServer() {
    server.handleClient();
}
