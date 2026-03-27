/**
 * @file iot_manager.c
 * @brief MQTT-based IoT manager for cloud communication.
 */

#include "iot_manager.h"
#include "config.h"
#include "error_logger.h"
#include "wifi_manager.h"

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "mqtt_client.h"

#define TAG "IOT_MGR"

static esp_mqtt_client_handle_t s_mqtt_client = NULL;
static iot_manager_state_t      s_state       = IOT_STATE_DISCONNECTED;
static iot_cmd_callback_t       s_cmd_cb      = NULL;
static bool                     s_initialized = false;
static uint32_t                 s_msg_count   = 0;

static void mqtt_event_handler(void *arg, esp_event_base_t base,
                                int32_t id, void *data)
{
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)data;

    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "MQTT connected");
        s_state = IOT_STATE_CONNECTED;
        iot_manager_subscribe(MQTT_TOPIC_CMD, 1);
        iot_manager_subscribe(MQTT_TOPIC_OTA, 1);
        iot_manager_publish(MQTT_TOPIC_STATUS, "{\"status\":\"online\"}", 1, true);
        break;

    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "MQTT disconnected");
        s_state = IOT_STATE_DISCONNECTED;
        break;

    case MQTT_EVENT_SUBSCRIBED:
        ESP_LOGI(TAG, "Subscribed, msg_id=%d", event->msg_id);
        break;

    case MQTT_EVENT_PUBLISHED:
        s_msg_count++;
        break;

    case MQTT_EVENT_DATA:
        ESP_LOGI(TAG, "MQTT RX topic=%.*s len=%d",
                 event->topic_len, event->topic, event->data_len);
        if (s_cmd_cb) {
            char topic[128] = {0};
            int  tlen = event->topic_len < 127 ? event->topic_len : 127;
            memcpy(topic, event->topic, tlen);
            s_cmd_cb(topic, (uint8_t *)event->data, event->data_len);
        }
        break;

    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "MQTT error");
        s_state = IOT_STATE_ERROR;
        error_logger_write(ERR_SRC_IOT, ESP_FAIL, "MQTT error event");
        break;

    default:
        break;
    }
}

esp_err_t iot_manager_init(void)
{
    if (s_initialized) return ESP_OK;

    esp_mqtt_client_config_t cfg = {
        .broker.address.uri       = MQTT_BROKER_URI,
        .broker.address.port      = MQTT_PORT,
        .credentials.client_id    = MQTT_CLIENT_ID,
        .credentials.username     = MQTT_USERNAME,
        .credentials.authentication.password = MQTT_PASSWORD,
        .session.keepalive        = MQTT_KEEPALIVE_SEC,
        .session.disable_clean_session = false,
    };

    s_mqtt_client = esp_mqtt_client_init(&cfg);
    if (!s_mqtt_client) {
        ESP_LOGE(TAG, "esp_mqtt_client_init failed");
        return ESP_FAIL;
    }

    ESP_RETURN_ON_ERROR(
        esp_mqtt_client_register_event(s_mqtt_client, ESP_EVENT_ANY_ID,
                                       mqtt_event_handler, NULL),
        TAG, "register_event failed");

    s_state = IOT_STATE_CONNECTING;
    ESP_RETURN_ON_ERROR(esp_mqtt_client_start(s_mqtt_client),
                        TAG, "mqtt_client_start failed");

    s_initialized = true;
    ESP_LOGI(TAG, "IoT manager initialised, broker: %s", MQTT_BROKER_URI);
    return ESP_OK;
}

esp_err_t iot_manager_deinit(void)
{
    if (s_mqtt_client) {
        iot_manager_publish(MQTT_TOPIC_STATUS, "{\"status\":\"offline\"}", 1, true);
        esp_mqtt_client_stop(s_mqtt_client);
        esp_mqtt_client_destroy(s_mqtt_client);
        s_mqtt_client = NULL;
    }
    s_initialized = false;
    return ESP_OK;
}

void iot_manager_process(void)
{
    static uint32_t s_tick = 0;
    s_tick++;
    if (s_tick % 30 == 0 && s_state == IOT_STATE_CONNECTED) {
        iot_manager_publish_metrics();
    }
}

esp_err_t iot_manager_publish(const char *topic, const char *msg,
                               int qos, bool retain)
{
    if (!s_mqtt_client || s_state != IOT_STATE_CONNECTED) return ESP_ERR_INVALID_STATE;
    int msg_id = esp_mqtt_client_publish(s_mqtt_client, topic, msg,
                                          strlen(msg), qos, retain ? 1 : 0);
    return (msg_id >= 0) ? ESP_OK : ESP_FAIL;
}

esp_err_t iot_manager_subscribe(const char *topic, int qos)
{
    if (!s_mqtt_client) return ESP_ERR_INVALID_STATE;
    int id = esp_mqtt_client_subscribe(s_mqtt_client, topic, qos);
    return (id >= 0) ? ESP_OK : ESP_FAIL;
}

iot_manager_state_t iot_manager_get_state(void) { return s_state; }

void iot_manager_register_cmd_callback(iot_cmd_callback_t cb) { s_cmd_cb = cb; }

esp_err_t iot_manager_publish_metrics(void)
{
    char buf[256];
    snprintf(buf, sizeof(buf),
             "{\"heap\":%lu,\"min_heap\":%lu,\"uptime\":%llu,\"wifi_rssi\":%d}",
             esp_get_free_heap_size(),
             esp_get_minimum_free_heap_size(),
             (unsigned long long)esp_timer_get_time() / 1000000ULL,
             wifi_manager_get_rssi());
    return iot_manager_publish(MQTT_TOPIC_METRICS, buf, 0, false);
}
