#ifndef CONFIG_H
#define CONFIG_H

#include "esp_system.h"

/* ─── Firmware Version ─────────────────────────────────────────── */
#define FW_VERSION_MAJOR        1
#define FW_VERSION_MINOR        0
#define FW_VERSION_PATCH        0
#define FW_VERSION_STRING       "1.0.0"
#define FW_BUILD_DATE           __DATE__
#define FW_BUILD_TIME           __TIME__

/* ─── WiFi ─────────────────────────────────────────────────────── */
#define WIFI_SSID_DEFAULT       "NethunterZ_Net"
#define WIFI_PASS_DEFAULT       "changeme123"
#define WIFI_AP_SSID            "NethunterZ_AP"
#define WIFI_AP_PASS            "nethunterz"
#define WIFI_AP_MAX_CONN        5
#define WIFI_MAX_RETRY          10
#define WIFI_RECONNECT_DELAY_MS 5000
#define WIFI_TASK_STACK         4096
#define WIFI_TASK_PRIORITY      5

/* ─── BLE ──────────────────────────────────────────────────────── */
#define BLE_DEVICE_NAME         "NethunterZ"
#define BLE_TASK_STACK          4096
#define BLE_TASK_PRIORITY       5
#define BLE_MTU_SIZE            517
/* UUIDs (128-bit, little-endian) */
#define BLE_SERVICE_UUID        0xAB, 0xCD, 0xEF, 0x01, 0x23, 0x45, 0x67, 0x89, \
                                0xAB, 0xCD, 0xEF, 0x01, 0x23, 0x45, 0x67, 0x89
#define BLE_CTRL_CHAR_UUID      0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, \
                                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01
#define BLE_OTA_CHAR_UUID       0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, \
                                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02
#define BLE_STATUS_CHAR_UUID    0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, \
                                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03

/* ─── MQTT / IoT ───────────────────────────────────────────────── */
#define MQTT_BROKER_URI         "mqtt://broker.nethunterz.local"
#define MQTT_PORT               1883
#define MQTT_CLIENT_ID          "nethunterz_esp32"
#define MQTT_USERNAME           ""
#define MQTT_PASSWORD           ""
#define MQTT_KEEPALIVE_SEC      60
#define MQTT_TOPIC_STATUS       "nethunterz/status"
#define MQTT_TOPIC_METRICS      "nethunterz/metrics"
#define MQTT_TOPIC_CMD          "nethunterz/cmd"
#define MQTT_TOPIC_OTA          "nethunterz/ota"
#define IOT_TASK_STACK          4096
#define IOT_TASK_PRIORITY       4

/* ─── OTA ──────────────────────────────────────────────────────── */
#define OTA_UPDATE_URL          "https://update.nethunterz.local/firmware.bin"
#define OTA_SERVER_CERT_PEM     NULL   /* Set to PEM string for TLS verification */
#define OTA_TASK_STACK          8192
#define OTA_TASK_PRIORITY       3
#define OTA_RECV_TIMEOUT_MS     5000
#define OTA_BUFFER_SIZE         1024

/* ─── Power Management ─────────────────────────────────────────── */
#define POWER_TASK_STACK        2048
#define POWER_TASK_PRIORITY     2
#define DEEP_SLEEP_DURATION_US  (30ULL * 1000000ULL)   /* 30 s */
#define LIGHT_SLEEP_DURATION_US (5ULL  * 1000000ULL)   /* 5 s  */
#define BATTERY_ADC_CHANNEL     ADC_CHANNEL_0
#define BATTERY_LOW_MV          3300
#define BATTERY_CRITICAL_MV     3100
#define CPU_FREQ_HIGH_MHZ       240
#define CPU_FREQ_MED_MHZ        160
#define CPU_FREQ_LOW_MHZ        80

/* ─── Error Logger ─────────────────────────────────────────────── */
#define ERR_LOG_TASK_STACK      2048
#define ERR_LOG_TASK_PRIORITY   3
#define ERR_LOG_NVS_NAMESPACE   "errlog"
#define ERR_LOG_MAX_ENTRIES     64
#define ERR_LOG_ENTRY_KEY_FMT   "err_%04u"

/* ─── Hardware Pins ────────────────────────────────────────────── */
#define PIN_STATUS_LED          2
#define PIN_BOOT_BTN            0
#define PIN_BATTERY_ADC         36
#define PIN_UART_TX             1
#define PIN_UART_RX             3

/* ─── NVS Keys ─────────────────────────────────────────────────── */
#define NVS_NAMESPACE           "nethunterz"
#define NVS_KEY_WIFI_SSID       "wifi_ssid"
#define NVS_KEY_WIFI_PASS       "wifi_pass"
#define NVS_KEY_MQTT_URI        "mqtt_uri"
#define NVS_KEY_BOOT_COUNT      "boot_cnt"
#define NVS_KEY_FW_SLOT         "fw_slot"

/* ─── Task notification bits ───────────────────────────────────── */
#define NOTIF_WIFI_CONNECTED    BIT(0)
#define NOTIF_WIFI_DISCONNECTED BIT(1)
#define NOTIF_BLE_CONNECTED     BIT(2)
#define NOTIF_OTA_TRIGGER       BIT(3)
#define NOTIF_SLEEP_REQUEST     BIT(4)

#endif /* CONFIG_H */
