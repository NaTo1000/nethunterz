#ifndef BLE_MANAGER_H
#define BLE_MANAGER_H

#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BLE_STATE_IDLE        = 0,
    BLE_STATE_ADVERTISING = 1,
    BLE_STATE_CONNECTED   = 2,
    BLE_STATE_OTA_MODE    = 3,
} ble_manager_state_t;

typedef void (*ble_ctrl_callback_t)(const uint8_t *data, size_t len);

esp_err_t         ble_manager_init(void);
esp_err_t         ble_manager_deinit(void);
void              ble_manager_process(void);
bool              ble_manager_is_connected(void);
ble_manager_state_t ble_manager_get_state(void);
esp_err_t         ble_manager_send_status(const uint8_t *data, size_t len);
esp_err_t         ble_manager_notify_ota(const char *msg);
void              ble_manager_register_ctrl_callback(ble_ctrl_callback_t cb);

#ifdef __cplusplus
}
#endif

#endif /* BLE_MANAGER_H */
