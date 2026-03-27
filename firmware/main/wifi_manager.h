#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include "esp_err.h"
#include "esp_wifi.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    WIFI_STATE_IDLE        = 0,
    WIFI_STATE_CONNECTING  = 1,
    WIFI_STATE_CONNECTED   = 2,
    WIFI_STATE_DISCONNECTED= 3,
    WIFI_STATE_AP_MODE     = 4,
    WIFI_STATE_ERROR       = 5,
} wifi_manager_state_t;

typedef struct {
    char     ssid[32];
    char     password[64];
    uint8_t  bssid[6];
    int8_t   rssi;
    uint8_t  channel;
    bool     is_connected;
} wifi_connection_info_t;

esp_err_t           wifi_manager_init(void);
esp_err_t           wifi_manager_deinit(void);
void                wifi_manager_process(void);
esp_err_t           wifi_manager_connect(const char *ssid, const char *pass);
esp_err_t           wifi_manager_disconnect(void);
esp_err_t           wifi_manager_start_ap(const char *ssid, const char *pass);
esp_err_t           wifi_manager_stop_ap(void);
wifi_manager_state_t wifi_manager_get_state(void);
esp_err_t           wifi_manager_get_connection_info(wifi_connection_info_t *info);
int8_t              wifi_manager_get_rssi(void);
bool                wifi_manager_is_connected(void);
esp_err_t           wifi_manager_scan(wifi_ap_record_t *ap_records, uint16_t *count);
void                wifi_manager_set_reconnect(bool enable);

#ifdef __cplusplus
}
#endif

#endif /* WIFI_MANAGER_H */
