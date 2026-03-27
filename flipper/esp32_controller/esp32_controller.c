/**
 * @file esp32_controller.c
 * @brief Flipper Zero app for controlling NethunterZ ESP32 firmware.
 *
 * Features:
 *   - Menu navigation (Up/Down/OK/Back)
 *   - ESP32 BLE connection status
 *   - Error log viewer (scrollable)
 *   - Firmware OTA update trigger
 *   - WiFi/BLE diagnostics
 *   - Frequency scanner (2400-2525 MHz)
 */

#include "esp32_controller.h"

static const char* MENU_ITEMS[MAX_MENU_ITEMS] = {
    "BLE Status",
    "Error Logs",
    "Trigger OTA",
    "Diagnostics",
    "Freq Scanner",
    "Exit",
};

/* ─── Draw callback ─────────────────────────────────────────────── */
void esp32_controller_draw(Canvas* canvas, void* ctx) {
    AppContext* app = (AppContext*)ctx;
    if (!app) return;

    canvas_clear(canvas);
    canvas_set_color(canvas, ColorBlack);

    switch (app->state) {
    /* ── Main Menu ─────────────────────────────────────────────── */
    case AppStateMenu:
        canvas_set_font(canvas, FontPrimary);
        canvas_draw_str(canvas, 2, 10, "NethunterZ ESP32");
        canvas_draw_line(canvas, 0, 12, 128, 12);

        for (uint8_t i = 0; i < MAX_MENU_ITEMS; i++) {
            uint8_t y = 24 + i * 10;
            if (i == app->menu_index) {
                canvas_draw_box(canvas, 0, y - 8, 128, 10);
                canvas_set_color(canvas, ColorWhite);
            }
            canvas_set_font(canvas, FontSecondary);
            canvas_draw_str(canvas, 4, y, MENU_ITEMS[i]);
            canvas_set_color(canvas, ColorBlack);
        }
        break;

    /* ── BLE Status ────────────────────────────────────────────── */
    case AppStateBLEStatus:
        canvas_set_font(canvas, FontPrimary);
        canvas_draw_str(canvas, 2, 10, "BLE Connection");
        canvas_draw_line(canvas, 0, 12, 128, 12);
        canvas_set_font(canvas, FontSecondary);

        const char* ble_states[] = {"Disconnected", "Scanning...", "Connected", "Error"};
        canvas_draw_str(canvas, 4, 24, "Status:");
        canvas_draw_str(canvas, 60, 24, ble_states[app->ble_conn_state]);

        if (app->ble_conn_state == BLEConnState_Connected) {
            canvas_draw_str(canvas, 4, 34, "FW:");
            canvas_draw_str(canvas, 30, 34, app->device_status.fw_version);
            canvas_draw_str(canvas, 4, 44, "IP:");
            canvas_draw_str(canvas, 30, 44, app->device_status.ip_addr);

            char rssi_buf[16];
            snprintf(rssi_buf, sizeof(rssi_buf), "%ld dBm", app->device_status.wifi_rssi);
            canvas_draw_str(canvas, 4, 54, "RSSI:");
            canvas_draw_str(canvas, 40, 54, rssi_buf);
        }

        canvas_draw_str(canvas, 4, 62, "[OK] Connect  [Back] Menu");
        break;

    /* ── Error Logs ────────────────────────────────────────────── */
    case AppStateErrorLogs:
        canvas_set_font(canvas, FontPrimary);
        canvas_draw_str(canvas, 2, 10, "Error Logs");
        canvas_draw_line(canvas, 0, 12, 128, 12);
        canvas_set_font(canvas, FontSecondary);

        if (app->error_count == 0) {
            canvas_draw_str(canvas, 4, 30, "No errors logged.");
        } else {
            char count_buf[24];
            snprintf(count_buf, sizeof(count_buf), "Count: %u", app->error_count);
            canvas_draw_str(canvas, 4, 22, count_buf);

            // Show scrollable list
            for (uint8_t i = 0; i < 3 && (app->error_scroll + i) < app->error_count; i++) {
                ErrorEntry* e = &app->errors[app->error_scroll + i];
                char line[32];
                snprintf(line, sizeof(line), "%lu: %s", e->timestamp, e->message);
                canvas_draw_str(canvas, 4, 32 + i * 12, line);
            }
            canvas_draw_str(canvas, 4, 62, "[Up/Dn] Scroll [Back]");
        }
        break;

    /* ── OTA Update ────────────────────────────────────────────── */
    case AppStateFirmwareOTA:
        canvas_set_font(canvas, FontPrimary);
        canvas_draw_str(canvas, 2, 10, "Firmware OTA");
        canvas_draw_line(canvas, 0, 12, 128, 12);
        canvas_set_font(canvas, FontSecondary);

        if (app->ota_in_progress) {
            char prog_buf[32];
            snprintf(prog_buf, sizeof(prog_buf), "Progress: %u%%", app->ota_progress);
            canvas_draw_str(canvas, 4, 30, "OTA in progress...");
            canvas_draw_str(canvas, 4, 42, prog_buf);
            // Draw progress bar
            uint8_t bar_w = (uint8_t)(app->ota_progress * 100 / 100);
            canvas_draw_frame(canvas, 4, 50, 100, 8);
            canvas_draw_box(canvas, 5, 51, bar_w, 6);
        } else {
            canvas_draw_str(canvas, 4, 26, "Send OTA trigger to ESP32");
            canvas_draw_str(canvas, 4, 36, "Device must be BLE connected");
            canvas_draw_str(canvas, 4, 56, "[OK] Trigger  [Back] Cancel");
        }
        break;

    /* ── Diagnostics ───────────────────────────────────────────── */
    case AppStateDiagnostics:
        canvas_set_font(canvas, FontPrimary);
        canvas_draw_str(canvas, 2, 10, "Diagnostics");
        canvas_draw_line(canvas, 0, 12, 128, 12);
        canvas_set_font(canvas, FontSecondary);

        if (app->ble_conn_state == BLEConnState_Connected) {
            char heap_buf[32];
            snprintf(heap_buf, sizeof(heap_buf), "Heap: %lu B", app->device_status.free_heap);
            canvas_draw_str(canvas, 4, 24, heap_buf);

            char batt_buf[32];
            snprintf(batt_buf, sizeof(batt_buf), "Batt: %lu mV", app->device_status.battery_mv);
            canvas_draw_str(canvas, 4, 34, batt_buf);

            char uptime_buf[32];
            snprintf(uptime_buf, sizeof(uptime_buf), "Up: %lu s", app->device_status.uptime_s);
            canvas_draw_str(canvas, 4, 44, uptime_buf);

            canvas_draw_str(canvas, 4, 54, app->device_status.wifi_connected ? "WiFi: OK" : "WiFi: --");
            canvas_draw_str(canvas, 64, 54, app->device_status.mqtt_connected ? "MQTT: OK" : "MQTT: --");
        } else {
            canvas_draw_str(canvas, 4, 32, "Not connected.");
            canvas_draw_str(canvas, 4, 44, "[Back] to connect first");
        }
        break;

    /* ── Freq Scanner ──────────────────────────────────────────── */
    case AppStateFreqScan:
        canvas_set_font(canvas, FontPrimary);
        canvas_draw_str(canvas, 2, 10, "Freq Scanner");
        canvas_draw_line(canvas, 0, 12, 128, 12);
        canvas_set_font(canvas, FontSecondary);
        canvas_draw_str(canvas, 4, 24, "Scan: 2400-2525 MHz");
        canvas_draw_str(canvas, 4, 36, app->freq_scan_result[0] ? app->freq_scan_result : "Press OK to scan");
        canvas_draw_str(canvas, 4, 56, "[OK] Scan  [Back] Menu");
        break;

    default:
        break;
    }
}

/* ─── Input callback ────────────────────────────────────────────── */
void esp32_controller_input(InputEvent* event, void* ctx) {
    AppContext* app = (AppContext*)ctx;
    if (!app || event->type != InputTypeShort) return;

    switch (app->state) {
    case AppStateMenu:
        if (event->key == InputKeyUp && app->menu_index > 0)
            app->menu_index--;
        else if (event->key == InputKeyDown && app->menu_index < MAX_MENU_ITEMS - 1)
            app->menu_index++;
        else if (event->key == InputKeyOk) {
            switch (app->menu_index) {
            case 0: app->state = AppStateBLEStatus;   break;
            case 1: app->state = AppStateErrorLogs;   esp32_controller_fetch_errors(app); break;
            case 2: app->state = AppStateFirmwareOTA; break;
            case 3: app->state = AppStateDiagnostics; break;
            case 4: app->state = AppStateFreqScan;    break;
            case 5: app->running = false;              break;
            }
        }
        break;

    case AppStateBLEStatus:
        if (event->key == InputKeyOk)
            esp32_controller_ble_connect(app);
        else if (event->key == InputKeyBack)
            app->state = AppStateMenu;
        break;

    case AppStateErrorLogs:
        if (event->key == InputKeyUp && app->error_scroll > 0)
            app->error_scroll--;
        else if (event->key == InputKeyDown && app->error_scroll + 3 < app->error_count)
            app->error_scroll++;
        else if (event->key == InputKeyBack)
            app->state = AppStateMenu;
        break;

    case AppStateFirmwareOTA:
        if (event->key == InputKeyOk && !app->ota_in_progress)
            esp32_controller_trigger_ota(app);
        else if (event->key == InputKeyBack)
            app->state = AppStateMenu;
        break;

    case AppStateDiagnostics:
        if (event->key == InputKeyBack)
            app->state = AppStateMenu;
        break;

    case AppStateFreqScan:
        if (event->key == InputKeyOk)
            esp32_controller_scan_frequencies(app);
        else if (event->key == InputKeyBack)
            app->state = AppStateMenu;
        break;

    default:
        break;
    }

    view_port_update(app->view_port);
}

/* ─── BLE operations ────────────────────────────────────────────── */
void esp32_controller_ble_connect(AppContext* app) {
    app->ble_conn_state = BLEConnState_Scanning;
    view_port_update(app->view_port);
    furi_delay_ms(BLE_SCAN_TIMEOUT_MS / 10);
    /* In a real implementation, use furi_hal_bt to scan for NethunterZ device */
    /* For now, simulate scan result */
    app->ble_conn_state = BLEConnState_Connected;
    snprintf(app->device_status.fw_version, sizeof(app->device_status.fw_version), "1.0.0");
    snprintf(app->device_status.ip_addr, sizeof(app->device_status.ip_addr), "192.168.1.100");
    app->device_status.wifi_rssi      = -65;
    app->device_status.free_heap      = 180000;
    app->device_status.battery_mv     = 3700;
    app->device_status.uptime_s       = 3600;
    app->device_status.wifi_connected = true;
    app->device_status.mqtt_connected = true;
    view_port_update(app->view_port);
}

void esp32_controller_ble_disconnect(AppContext* app) {
    app->ble_conn_state = BLEConnState_Disconnected;
}

void esp32_controller_fetch_errors(AppContext* app) {
    /* Simulate fetching error logs over BLE */
    app->error_count  = 2;
    app->error_scroll = 0;
    app->errors[0].timestamp = 1234567;
    app->errors[0].source    = 0; /* WiFi */
    app->errors[0].code      = -1;
    snprintf(app->errors[0].message, sizeof(app->errors[0].message), "WiFi reconnect #3");
    app->errors[1].timestamp = 1234890;
    app->errors[1].source    = 2; /* IoT */
    app->errors[1].code      = -2;
    snprintf(app->errors[1].message, sizeof(app->errors[1].message), "MQTT disconnect");
}

void esp32_controller_trigger_ota(AppContext* app) {
    if (app->ble_conn_state != BLEConnState_Connected) return;
    app->ota_in_progress = true;
    app->ota_progress    = 0;
    view_port_update(app->view_port);
    /* Send OTA command over BLE – simulated here */
    for (uint8_t p = 0; p <= 100; p += 10) {
        app->ota_progress = p;
        furi_delay_ms(200);
        view_port_update(app->view_port);
    }
    app->ota_in_progress = false;
    view_port_update(app->view_port);
}

void esp32_controller_run_diagnostics(AppContext* app) {
    if (app->ble_conn_state != BLEConnState_Connected) return;
    /* In real implementation, request diagnostics over BLE */
    view_port_update(app->view_port);
}

void esp32_controller_scan_frequencies(AppContext* app) {
    /* Simulate 2.4 GHz channel scan */
    uint8_t best_channel = 6;
    int8_t  best_rssi    = -90;
    for (uint8_t ch = 1; ch <= 13; ch++) {
        /* In real implementation, use ESP32 scan results via BLE */
        int8_t simulated = -50 - (int8_t)(ch * 3);
        if (simulated < best_rssi) {
            best_rssi    = simulated;
            best_channel = ch;
        }
    }
    snprintf(app->freq_scan_result, sizeof(app->freq_scan_result),
             "Best ch: %u (%d dBm)", best_channel, best_rssi);
    view_port_update(app->view_port);
}

/* ─── App entry point ───────────────────────────────────────────── */
int32_t esp32_controller_app(void* p) {
    UNUSED(p);
    FURI_LOG_I(TAG, "ESP32 Controller started");

    AppContext* app = malloc(sizeof(AppContext));
    if (!app) return -1;
    memset(app, 0, sizeof(AppContext));
    app->running        = true;
    app->state          = AppStateMenu;
    app->ble_conn_state = BLEConnState_Disconnected;

    app->gui       = furi_record_open(RECORD_GUI);
    app->view_port = view_port_alloc();
    view_port_draw_callback_set(app->view_port, esp32_controller_draw, app);
    view_port_input_callback_set(app->view_port, esp32_controller_input, app);
    gui_add_view_port(app->gui, app->view_port, GuiLayerFullscreen);

    app->event_queue = furi_message_queue_alloc(8, sizeof(InputEvent));

    while (app->running) {
        view_port_update(app->view_port);
        furi_delay_ms(100);
    }

    gui_remove_view_port(app->gui, app->view_port);
    view_port_free(app->view_port);
    furi_message_queue_free(app->event_queue);
    furi_record_close(RECORD_GUI);
    free(app);
    FURI_LOG_I(TAG, "ESP32 Controller stopped");
    return 0;
}
