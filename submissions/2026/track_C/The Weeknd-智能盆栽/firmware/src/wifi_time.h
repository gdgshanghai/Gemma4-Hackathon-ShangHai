#ifndef WIFI_TIME_H
#define WIFI_TIME_H

void initWifiTime();
void updateWifiTime();
bool getFormattedTime(char* buffer, int bufferSize);
void printWifiStatus();
void getLocalIPStr(char* buffer, int bufferSize);

#endif
