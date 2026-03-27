#ifndef IOT_MANAGER_H
#define IOT_MANAGER_H

#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    IOT_STATE_DISCONNECTED = 0,
    IOT_STATE_CONNECTING   = 1,
    IOT_STATE_CONNECTED    = 2,
    IOT_STATE_ERROR        = 3,
} iot_manager_state_t;

typedef void (*iot_cmd_callback_t)(const char *topic, const uint8_t *data, size_t len);

esp_err_t         iot_manager_init(void);
esp_err_t         iot_manager_deinit(void);
void              iot_manager_process(void);
esp_err_t         iot_manager_publish(const char *topic, const char *msg, int qos, bool retain);
esp_err_t         iot_manager_subscribe(const char *topic, int qos);
iot_manager_state_t iot_manager_get_state(void);
void              iot_manager_register_cmd_callback(iot_cmd_callback_t cb);
esp_err_t         iot_manager_publish_metrics(void);

#ifdef __cplusplus
}
#endif

#endif /* IOT_MANAGER_H */
