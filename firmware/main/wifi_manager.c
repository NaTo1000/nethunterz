/**
 * @file wifi_manager.c
 * @brief WiFi station and AP management with automatic reconnect logic.
 */

#include "wifi_manager.h"
#include "config.h"
#include "error_logger.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs.h"

#define TAG "WIFI_MGR"

/* External globals from main.c */
extern EventGroupHandle_t g_system_events;

/* ─── Internal state ────────────────────────────────────────────── */
static wifi_manager_state_t  s_state          = WIFI_STATE_IDLE;
static wifi_connection_info_t s_conn_info     = {0};
static esp_netif_t           *s_sta_netif     = NULL;
static esp_netif_t           *s_ap_netif      = NULL;
static int                    s_retry_count   = 0;
static bool                   s_reconnect_en  = true;
static bool                   s_initialized   = false;
static TickType_t             s_last_reconnect= 0;

/* ─── Event handler ─────────────────────────────────────────────── */
static void wifi_event_handler(void *arg, esp_event_base_t base,
                                int32_t id, void *data)
{
    if (base == WIFI_EVENT) {
        switch (id) {
        case WIFI_EVENT_STA_START:
            ESP_LOGI(TAG, "STA started, connecting...");
            s_state = WIFI_STATE_CONNECTING;
            esp_wifi_connect();
            break;

        case WIFI_EVENT_STA_DISCONNECTED: {
            wifi_event_sta_disconnected_t *ev =
                (wifi_event_sta_disconnected_t *)data;
            ESP_LOGW(TAG, "STA disconnected (reason %d)", ev->reason);
            s_state = WIFI_STATE_DISCONNECTED;
            s_conn_info.is_connected = false;
            xEventGroupClearBits(g_system_events, NOTIF_WIFI_CONNECTED);
            xEventGroupSetBits(g_system_events, NOTIF_WIFI_DISCONNECTED);

            if (s_reconnect_en && s_retry_count < WIFI_MAX_RETRY) {
                s_retry_count++;
                ESP_LOGI(TAG, "Retry %d/%d", s_retry_count, WIFI_MAX_RETRY);
                vTaskDelay(pdMS_TO_TICKS(WIFI_RECONNECT_DELAY_MS));
                esp_wifi_connect();
            } else {
                ESP_LOGE(TAG, "Max retries exceeded, entering AP mode");
                wifi_manager_start_ap(WIFI_AP_SSID, WIFI_AP_PASS);
            }
            break;
        }

        case WIFI_EVENT_AP_STACONNECTED: {
            wifi_event_ap_staconnected_t *ev =
                (wifi_event_ap_staconnected_t *)data;
            ESP_LOGI(TAG, "AP: client connected " MACSTR, MAC2STR(ev->mac));
            break;
        }

        case WIFI_EVENT_AP_STADISCONNECTED: {
            wifi_event_ap_stadisconnected_t *ev =
                (wifi_event_ap_stadisconnected_t *)data;
            ESP_LOGI(TAG, "AP: client disconnected " MACSTR, MAC2STR(ev->mac));
            break;
        }

        default:
            break;
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *ev = (ip_event_got_ip_t *)data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&ev->ip_info.ip));
        s_state = WIFI_STATE_CONNECTED;
        s_conn_info.is_connected = true;
        s_retry_count = 0;
        xEventGroupSetBits(g_system_events, NOTIF_WIFI_CONNECTED);
        xEventGroupClearBits(g_system_events, NOTIF_WIFI_DISCONNECTED);
    }
}

/* ─── Public API ────────────────────────────────────────────────── */

esp_err_t wifi_manager_init(void)
{
    if (s_initialized) return ESP_OK;

    /* Create default netif instances */
    s_sta_netif = esp_netif_create_default_wifi_sta();
    if (!s_sta_netif) return ESP_FAIL;

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&cfg), TAG, "esp_wifi_init failed");

    /* Register event handlers */
    ESP_RETURN_ON_ERROR(
        esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                            wifi_event_handler, NULL, NULL),
        TAG, "Register WIFI_EVENT failed");

    ESP_RETURN_ON_ERROR(
        esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                            wifi_event_handler, NULL, NULL),
        TAG, "Register IP_EVENT failed");

    /* Load credentials from NVS */
    char ssid[32] = WIFI_SSID_DEFAULT;
    char pass[64] = WIFI_PASS_DEFAULT;
    nvs_handle_t nvs;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs) == ESP_OK) {
        size_t len = sizeof(ssid);
        nvs_get_str(nvs, NVS_KEY_WIFI_SSID, ssid, &len);
        len = sizeof(pass);
        nvs_get_str(nvs, NVS_KEY_WIFI_PASS, pass, &len);
        nvs_close(nvs);
    }

    ESP_RETURN_ON_ERROR(wifi_manager_connect(ssid, pass),
                        TAG, "Initial connect failed");

    s_initialized = true;
    ESP_LOGI(TAG, "WiFi manager initialised");
    return ESP_OK;
}

esp_err_t wifi_manager_deinit(void)
{
    esp_wifi_stop();
    esp_wifi_deinit();
    if (s_sta_netif) { esp_netif_destroy(s_sta_netif); s_sta_netif = NULL; }
    if (s_ap_netif)  { esp_netif_destroy(s_ap_netif);  s_ap_netif  = NULL; }
    s_initialized = false;
    return ESP_OK;
}

void wifi_manager_process(void)
{
    /* Periodic RSSI update when connected */
    if (s_state == WIFI_STATE_CONNECTED) {
        wifi_ap_record_t ap;
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            s_conn_info.rssi    = ap.rssi;
            s_conn_info.channel = ap.primary;
            memcpy(s_conn_info.bssid, ap.bssid, 6);
        }
    }
}

esp_err_t wifi_manager_connect(const char *ssid, const char *pass)
{
    if (!ssid || strlen(ssid) == 0) return ESP_ERR_INVALID_ARG;

    wifi_config_t cfg = {0};
    strlcpy((char *)cfg.sta.ssid,     ssid, sizeof(cfg.sta.ssid));
    strlcpy((char *)cfg.sta.password, pass, sizeof(cfg.sta.password));
    cfg.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    cfg.sta.pmf_cfg.capable    = true;
    cfg.sta.pmf_cfg.required   = false;

    strlcpy(s_conn_info.ssid, ssid, sizeof(s_conn_info.ssid));

    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA),    TAG, "set_mode STA");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &cfg), TAG, "set_config");
    ESP_RETURN_ON_ERROR(esp_wifi_start(),                    TAG, "wifi_start");

    return ESP_OK;
}

esp_err_t wifi_manager_disconnect(void)
{
    s_reconnect_en = false;
    esp_wifi_disconnect();
    s_state = WIFI_STATE_IDLE;
    return ESP_OK;
}

esp_err_t wifi_manager_start_ap(const char *ssid, const char *pass)
{
    if (!s_ap_netif) {
        s_ap_netif = esp_netif_create_default_wifi_ap();
    }

    wifi_config_t cfg = {0};
    strlcpy((char *)cfg.ap.ssid,     ssid, sizeof(cfg.ap.ssid));
    strlcpy((char *)cfg.ap.password, pass, sizeof(cfg.ap.password));
    cfg.ap.ssid_len       = strlen(ssid);
    cfg.ap.max_connection = WIFI_AP_MAX_CONN;
    cfg.ap.authmode       = WIFI_AUTH_WPA2_PSK;
    if (strlen(pass) == 0) cfg.ap.authmode = WIFI_AUTH_OPEN;

    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_APSTA), TAG, "set_mode AP");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_AP, &cfg), TAG, "set_config AP");

    s_state = WIFI_STATE_AP_MODE;
    ESP_LOGI(TAG, "AP started: SSID=%s", ssid);
    return ESP_OK;
}

esp_err_t wifi_manager_stop_ap(void)
{
    esp_wifi_set_mode(WIFI_MODE_STA);
    return ESP_OK;
}

wifi_manager_state_t wifi_manager_get_state(void) { return s_state; }

esp_err_t wifi_manager_get_connection_info(wifi_connection_info_t *info)
{
    if (!info) return ESP_ERR_INVALID_ARG;
    memcpy(info, &s_conn_info, sizeof(*info));
    return ESP_OK;
}

int8_t wifi_manager_get_rssi(void) { return s_conn_info.rssi; }
bool   wifi_manager_is_connected(void) { return s_conn_info.is_connected; }

esp_err_t wifi_manager_scan(wifi_ap_record_t *ap_records, uint16_t *count)
{
    if (!ap_records || !count) return ESP_ERR_INVALID_ARG;
    wifi_scan_config_t scan_cfg = { .show_hidden = true };
    ESP_RETURN_ON_ERROR(esp_wifi_scan_start(&scan_cfg, true), TAG, "scan_start");
    return esp_wifi_scan_get_ap_records(count, ap_records);
}

void wifi_manager_set_reconnect(bool enable) { s_reconnect_en = enable; }
