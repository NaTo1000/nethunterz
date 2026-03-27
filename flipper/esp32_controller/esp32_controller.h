#pragma once

#include <furi.h>
#include <furi_hal.h>
#include <gui/gui.h>
#include <gui/view_port.h>
#include <input/input.h>
#include <notification/notification_messages.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#define TAG "ESP32Ctrl"
#define MAX_ERROR_ENTRIES 32
#define MAX_MENU_ITEMS    6
#define BLE_SCAN_TIMEOUT_MS 5000

typedef enum {
    AppStateMenu        = 0,
    AppStateBLEStatus   = 1,
    AppStateErrorLogs   = 2,
    AppStateFirmwareOTA = 3,
    AppStateDiagnostics = 4,
    AppStateFreqScan    = 5,
} AppState;

typedef enum {
    BLEConnState_Disconnected = 0,
    BLEConnState_Scanning     = 1,
    BLEConnState_Connected    = 2,
    BLEConnState_Error        = 3,
} BLEConnState;

typedef struct {
    uint32_t timestamp;
    uint8_t  source;
    int32_t  code;
    char     message[80];
} ErrorEntry;

typedef struct {
    uint32_t uptime_s;
    int32_t  wifi_rssi;
    uint32_t free_heap;
    uint32_t battery_mv;
    char     fw_version[16];
    char     ip_addr[16];
    bool     wifi_connected;
    bool     ble_connected;
    bool     mqtt_connected;
} DeviceStatus;

typedef struct {
    Gui*            gui;
    ViewPort*       view_port;
    FuriMessageQueue* event_queue;

    AppState        state;
    uint8_t         menu_index;
    BLEConnState    ble_conn_state;
    DeviceStatus    device_status;
    ErrorEntry      errors[MAX_ERROR_ENTRIES];
    uint8_t         error_count;
    uint8_t         error_scroll;
    bool            ota_in_progress;
    uint8_t         ota_progress;
    char            freq_scan_result[64];
    bool            running;
} AppContext;

void esp32_controller_draw(Canvas* canvas, void* ctx);
void esp32_controller_input(InputEvent* event, void* ctx);
void esp32_controller_ble_connect(AppContext* app);
void esp32_controller_ble_disconnect(AppContext* app);
void esp32_controller_fetch_errors(AppContext* app);
void esp32_controller_trigger_ota(AppContext* app);
void esp32_controller_run_diagnostics(AppContext* app);
void esp32_controller_scan_frequencies(AppContext* app);
int32_t esp32_controller_app(void* p);
