#include "bluetooth_manager.h"

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

#include "plant_controller.h"

namespace {
const char* DEVICE_NAME = "Weeknd";
const char* SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E";
const char* RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E";
const char* TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E";

BLECharacteristic* txCharacteristic = nullptr;
bool clientConnected = false;
String pendingAck;
bool hasPendingAck = false;
String bubbleMessageStorage;

String trimString(const String& value) {
    int start = 0;
    int end = value.length();

    while (start < end && isspace(static_cast<unsigned char>(value[start]))) {
        ++start;
    }

    while (end > start && isspace(static_cast<unsigned char>(value[end - 1]))) {
        --end;
    }

    return value.substring(start, end);
}

PlantEmotion parseEmotion(const String& value, bool& ok) {
    ok = true;

    if (value == "NORMAL") return EMOTION_NORMAL;
    if (value == "TOUCH") return EMOTION_TOUCH;
    if (value == "THIRSTY") return EMOTION_THIRSTY;
    if (value == "DROWN") return EMOTION_DROWN;
    if (value == "HOT") return EMOTION_HOT;
    if (value == "COLD") return EMOTION_COLD;
    if (value == "DEADLY") return EMOTION_DEADLY;

    ok = false;
    return EMOTION_NORMAL;
}

void queueAck(const String& message) {
    pendingAck = message;
    hasPendingAck = true;
}

void handleBleCommand(const String& rawCommand) {
    String command = trimString(rawCommand);
    command.toUpperCase();

    if (command.length() == 0) {
        queueAck("ERR:EMPTY");
        return;
    }

    Serial.print("BLE RX: ");
    Serial.println(command);

    if (command == "WAKE") {
        wakePlant();
        queueAck("OK:WAKE");
        return;
    }

    if (command == "RESET_ENV") {
        resetEnvironmentToDefaults();
        renderAwakePlant();
        queueAck("OK:RESET_ENV");
        return;
    }

    if (command == "CLEAR_EMOTION") {
        clearAppEmotionOverride();
        queueAck("OK:CLEAR_EMOTION");
        return;
    }

    if (command.startsWith("TEMP:")) {
        int temperatureC = command.substring(5).toInt();
        setTemperatureC(temperatureC);
        renderAwakePlant();
        queueAck("OK:TEMP");
        return;
    }

    if (command.startsWith("RAW:")) {
        int moistureRaw = command.substring(4).toInt();
        setMoistureRaw(moistureRaw);
        renderAwakePlant();
        queueAck("OK:RAW");
        return;
    }

    if (command.startsWith("ENV:")) {
        int commaIndex = command.indexOf(',');
        if (commaIndex < 0) {
            queueAck("ERR:ENV_FORMAT");
            return;
        }

        int temperatureC = command.substring(4, commaIndex).toInt();
        int moistureRaw = command.substring(commaIndex + 1).toInt();
        setAppEnvironment(temperatureC, moistureRaw);
        renderAwakePlant();
        queueAck("OK:ENV");
        return;
    }

    if (command.startsWith("EMOTION:")) {
        bool ok = false;
        PlantEmotion emotion = parseEmotion(command.substring(8), ok);
        if (!ok) {
            queueAck("ERR:EMOTION");
            return;
        }

        setAppEmotionOverride(emotion);
        queueAck("OK:EMOTION");
        return;
    }

    if (command == "GET_DATA") {
        String data = "DATA:";
        data += "T=" + String(getTemperatureC()) + ",";
        data += "M=" + String(getMoistureRaw()) + ",";
        data += "E=" + String((int)getCurrentEmotion()) + ",";
        data += "S=" + String(isPlantSleeping() ? "1" : "0");
        queueAck(data);
        return;
    }

    if (command.startsWith("BUBBLE:")) {
        bubbleMessageStorage = trimString(rawCommand.substring(7));
        if (bubbleMessageStorage.length() == 0) {
            queueAck("ERR:BUBBLE");
            return;
        }

        wakePlant();
        showBubble(bubbleMessageStorage.c_str());
        queueAck("OK:BUBBLE");
        return;
    }

    queueAck("ERR:UNKNOWN");
}

class WeekndServerCallbacks : public BLEServerCallbacks {
public:
    void onConnect(BLEServer* pServer) override {
        clientConnected = true;
        Serial.println("BLE: client connected");
    }

    void onDisconnect(BLEServer* pServer) override {
        clientConnected = false;
        Serial.println("BLE: client disconnected");
        BLEDevice::startAdvertising();
    }
};

class WeekndRxCallbacks : public BLECharacteristicCallbacks {
public:
    void onWrite(BLECharacteristic* characteristic) override {
        std::string value = characteristic->getValue();
        if (value.empty()) {
            queueAck("ERR:EMPTY");
            return;
        }

        handleBleCommand(String(value.c_str()));
    }
};
}  // namespace

void initBluetoothManager() {
    BLEDevice::init(DEVICE_NAME);

    BLEServer* server = BLEDevice::createServer();
    server->setCallbacks(new WeekndServerCallbacks());

    BLEService* service = server->createService(SERVICE_UUID);

    BLECharacteristic* rxCharacteristic = service->createCharacteristic(
        RX_CHAR_UUID,
        BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
    );
    rxCharacteristic->setCallbacks(new WeekndRxCallbacks());

    txCharacteristic = service->createCharacteristic(
        TX_CHAR_UUID,
        BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_READ
    );
    txCharacteristic->setValue("READY");

    service->start();

    BLEAdvertising* advertising = BLEDevice::getAdvertising();
    advertising->addServiceUUID(SERVICE_UUID);
    advertising->setScanResponse(true);
    advertising->setMinPreferred(0x06);
    advertising->setMinPreferred(0x12);
    BLEDevice::startAdvertising();

    Serial.println("BLE Started: Weeknd");
    Serial.println("BLE Commands: WAKE | RESET_ENV | CLEAR_EMOTION | GET_DATA | TEMP:28 | RAW:800 | ENV:28,800 | EMOTION:NORMAL | BUBBLE:text");
}

void updateBluetoothManager() {
    if (!hasPendingAck || txCharacteristic == nullptr) {
        return;
    }

    txCharacteristic->setValue(pendingAck.c_str());
    if (clientConnected) {
        txCharacteristic->notify();
    }

    Serial.print("BLE TX: ");
    Serial.println(pendingAck);
    hasPendingAck = false;
}
