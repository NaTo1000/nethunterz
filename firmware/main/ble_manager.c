/**
 * @file ble_manager.c
 * @brief BLE GATT server with control characteristic, OTA notification,
 *        and status reporting for phone connectivity.
 */

#include "ble_manager.h"
#include "config.h"
#include "error_logger.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_bt.h"
#include "esp_gap_ble_api.h"
#include "esp_gatts_api.h"
#include "esp_bt_main.h"
#include "esp_gatt_common_api.h"

#define TAG "BLE_MGR"

#define PROFILE_NUM             1
#define PROFILE_APP_IDX         0
#define ESP_APP_ID              0x55
#define SVC_INST_ID             0

/* Number of handles: service + 3 characteristics × 2 (value + CCC) + 3 */
#define HANDLE_COUNT            10

/* Attribute indices */
enum {
    IDX_SVC               = 0,
    IDX_CTRL_CHAR,
    IDX_CTRL_VAL,
    IDX_OTA_CHAR,
    IDX_OTA_VAL,
    IDX_OTA_CCC,
    IDX_STATUS_CHAR,
    IDX_STATUS_VAL,
    IDX_STATUS_CCC,
    IDX_MAX,
};

static const uint16_t PRIMARY_SERVICE_UUID    = ESP_GATT_UUID_PRI_SERVICE;
static const uint16_t CHAR_DECLARE_UUID       = ESP_GATT_UUID_CHAR_DECLARE;
static const uint16_t CHAR_CLIENT_CONFIG_UUID = ESP_GATT_UUID_CHAR_CLIENT_CONFIG;
static const uint8_t  CHAR_PROP_RW            = ESP_GATT_CHAR_PROP_BIT_READ |
                                                 ESP_GATT_CHAR_PROP_BIT_WRITE;
static const uint8_t  CHAR_PROP_NOTIFY        = ESP_GATT_CHAR_PROP_BIT_NOTIFY;

static const uint8_t  SERVICE_UUID[16]        = { BLE_SERVICE_UUID };
static const uint8_t  CTRL_UUID[16]           = { BLE_CTRL_CHAR_UUID };
static const uint8_t  OTA_UUID[16]            = { BLE_OTA_CHAR_UUID };
static const uint8_t  STATUS_UUID[16]         = { BLE_STATUS_CHAR_UUID };

static uint8_t  s_ctrl_val[256]     = {0};
static uint8_t  s_ota_val[256]      = {0};
static uint8_t  s_status_val[256]   = {0};
static uint16_t s_ota_ccc           = 0;
static uint16_t s_status_ccc        = 0;

static uint16_t s_handle_table[IDX_MAX];
static uint16_t s_conn_id           = 0xFFFF;
static uint16_t s_gatts_if          = ESP_GATT_IF_NONE;

static ble_manager_state_t  s_state = BLE_STATE_IDLE;
static ble_ctrl_callback_t  s_ctrl_cb = NULL;

/* ─── GATT DB ───────────────────────────────────────────────────── */
static const esp_gatts_attr_db_t s_gatt_db[IDX_MAX] = {
    [IDX_SVC] = {
        { ESP_GATT_AUTO_RSP },
        { ESP_UUID_LEN_16, (uint8_t *)&PRIMARY_SERVICE_UUID,
          ESP_GATT_PERM_READ, sizeof(SERVICE_UUID), sizeof(SERVICE_UUID),
          (uint8_t *)SERVICE_UUID }
    },
    [IDX_CTRL_CHAR] = {
        { ESP_GATT_AUTO_RSP },
        { ESP_UUID_LEN_16, (uint8_t *)&CHAR_DECLARE_UUID,
          ESP_GATT_PERM_READ, sizeof(uint8_t), sizeof(uint8_t),
          (uint8_t *)&CHAR_PROP_RW }
    },
    [IDX_CTRL_VAL] = {
        { ESP_GATT_AUTO_RSP },
        { ESP_UUID_LEN_128, (uint8_t *)CTRL_UUID,
          ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE,
          sizeof(s_ctrl_val), 0, NULL }
    },
    [IDX_OTA_CHAR] = {
        { ESP_GATT_AUTO_RSP },
        { ESP_UUID_LEN_16, (uint8_t *)&CHAR_DECLARE_UUID,
          ESP_GATT_PERM_READ, sizeof(uint8_t), sizeof(uint8_t),
          (uint8_t *)&CHAR_PROP_NOTIFY }
    },
    [IDX_OTA_VAL] = {
        { ESP_GATT_AUTO_RSP },
        { ESP_UUID_LEN_128, (uint8_t *)OTA_UUID,
          ESP_GATT_PERM_READ,
          sizeof(s_ota_val), 0, NULL }
    },
    [IDX_OTA_CCC] = {
        { ESP_GATT_AUTO_RSP },
        { ESP_UUID_LEN_16, (uint8_t *)&CHAR_CLIENT_CONFIG_UUID,
          ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE,
          sizeof(uint16_t), sizeof(uint16_t), (uint8_t *)&s_ota_ccc }
    },
    [IDX_STATUS_CHAR] = {
        { ESP_GATT_AUTO_RSP },
        { ESP_UUID_LEN_16, (uint8_t *)&CHAR_DECLARE_UUID,
          ESP_GATT_PERM_READ, sizeof(uint8_t), sizeof(uint8_t),
          (uint8_t *)&CHAR_PROP_NOTIFY }
    },
    [IDX_STATUS_VAL] = {
        { ESP_GATT_AUTO_RSP },
        { ESP_UUID_LEN_128, (uint8_t *)STATUS_UUID,
          ESP_GATT_PERM_READ,
          sizeof(s_status_val), 0, NULL }
    },
    [IDX_STATUS_CCC] = {
        { ESP_GATT_AUTO_RSP },
        { ESP_UUID_LEN_16, (uint8_t *)&CHAR_CLIENT_CONFIG_UUID,
          ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE,
          sizeof(uint16_t), sizeof(uint16_t), (uint8_t *)&s_status_ccc }
    },
};

/* ─── Advertising data ──────────────────────────────────────────── */
static esp_ble_adv_data_t s_adv_data = {
    .set_scan_rsp        = false,
    .include_name        = true,
    .include_txpower     = false,
    .min_interval        = 0x0006,
    .max_interval        = 0x0010,
    .appearance          = 0x00,
    .manufacturer_len    = 0,
    .p_manufacturer_data = NULL,
    .service_data_len    = 0,
    .p_service_data      = NULL,
    .service_uuid_len    = 0,
    .p_service_uuid      = NULL,
    .flag                = (ESP_BLE_ADV_FLAG_GEN_DISC | ESP_BLE_ADV_FLAG_BREDR_NOT_SPT),
};

static esp_ble_adv_params_t s_adv_params = {
    .adv_int_min        = 0x20,
    .adv_int_max        = 0x40,
    .adv_type           = ADV_TYPE_IND,
    .own_addr_type      = BLE_ADDR_TYPE_PUBLIC,
    .channel_map        = ADV_CHNL_ALL,
    .adv_filter_policy  = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
};

/* ─── GAP event handler ─────────────────────────────────────────── */
static void gap_event_handler(esp_gap_ble_cb_event_t event,
                               esp_ble_gap_cb_param_t *param)
{
    switch (event) {
    case ESP_GAP_BLE_ADV_DATA_SET_COMPLETE_EVT:
        esp_ble_gap_start_advertising(&s_adv_params);
        s_state = BLE_STATE_ADVERTISING;
        break;
    case ESP_GAP_BLE_ADV_START_COMPLETE_EVT:
        if (param->adv_start_cmpl.status != ESP_BT_STATUS_SUCCESS) {
            ESP_LOGE(TAG, "Advertising start failed");
        } else {
            ESP_LOGI(TAG, "Advertising started");
        }
        break;
    case ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT:
        ESP_LOGI(TAG, "Advertising stopped");
        break;
    case ESP_GAP_BLE_UPDATE_CONN_PARAMS_EVT:
        ESP_LOGI(TAG, "Conn params updated: interval=%d latency=%d timeout=%d",
                 param->update_conn_params.conn_int,
                 param->update_conn_params.latency,
                 param->update_conn_params.timeout);
        break;
    default:
        break;
    }
}

/* ─── GATTS event handler ───────────────────────────────────────── */
static void gatts_event_handler(esp_gatts_cb_event_t event,
                                 esp_gatt_if_t gatts_if,
                                 esp_ble_gatts_cb_param_t *param)
{
    switch (event) {
    case ESP_GATTS_REG_EVT:
        s_gatts_if = gatts_if;
        esp_ble_gap_set_device_name(BLE_DEVICE_NAME);
        esp_ble_gap_config_adv_data(&s_adv_data);
        esp_ble_gatts_create_attr_tab(s_gatt_db, gatts_if, IDX_MAX, SVC_INST_ID);
        break;

    case ESP_GATTS_CREAT_ATTR_TAB_EVT:
        if (param->add_attr_tab.status != ESP_GATT_OK) {
            ESP_LOGE(TAG, "create attr table error %d",
                     param->add_attr_tab.status);
        } else {
            memcpy(s_handle_table, param->add_attr_tab.handles,
                   sizeof(s_handle_table));
            esp_ble_gatts_start_service(s_handle_table[IDX_SVC]);
        }
        break;

    case ESP_GATTS_CONNECT_EVT:
        s_conn_id = param->connect.conn_id;
        s_state   = BLE_STATE_CONNECTED;
        ESP_LOGI(TAG, "Client connected, conn_id=%d", s_conn_id);
        esp_ble_conn_update_params_t params = {
            .latency   = 0,
            .max_int   = 0x20,
            .min_int   = 0x10,
            .timeout   = 400,
        };
        memcpy(params.bda, param->connect.remote_bda, sizeof(params.bda));
        esp_ble_gap_update_conn_params(&params);
        break;

    case ESP_GATTS_DISCONNECT_EVT:
        s_conn_id = 0xFFFF;
        s_state   = BLE_STATE_IDLE;
        ESP_LOGI(TAG, "Client disconnected, restarting advertising");
        esp_ble_gap_start_advertising(&s_adv_params);
        s_state = BLE_STATE_ADVERTISING;
        break;

    case ESP_GATTS_WRITE_EVT:
        if (!param->write.is_prep &&
            param->write.handle == s_handle_table[IDX_CTRL_VAL]) {
            size_t len = param->write.len;
            if (len > sizeof(s_ctrl_val)) len = sizeof(s_ctrl_val);
            memcpy(s_ctrl_val, param->write.value, len);
            ESP_LOGI(TAG, "CTRL write %d bytes", len);
            if (s_ctrl_cb) s_ctrl_cb(s_ctrl_val, len);
        }
        break;

    case ESP_GATTS_MTU_EVT:
        ESP_LOGI(TAG, "MTU set to %d", param->mtu.mtu);
        break;

    default:
        break;
    }
}

/* ─── Public API ────────────────────────────────────────────────── */

esp_err_t ble_manager_init(void)
{
    ESP_RETURN_ON_ERROR(esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT),
                        TAG, "mem_release classic");

    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_bt_controller_init(&bt_cfg), TAG, "bt_ctrl_init");
    ESP_RETURN_ON_ERROR(esp_bt_controller_enable(ESP_BT_MODE_BLE), TAG, "bt_ctrl_en");
    ESP_RETURN_ON_ERROR(esp_bluedroid_init(),   TAG, "bluedroid_init");
    ESP_RETURN_ON_ERROR(esp_bluedroid_enable(), TAG, "bluedroid_enable");

    ESP_RETURN_ON_ERROR(esp_ble_gatts_register_callback(gatts_event_handler),
                        TAG, "gatts_register_cb");
    ESP_RETURN_ON_ERROR(esp_ble_gap_register_callback(gap_event_handler),
                        TAG, "gap_register_cb");
    ESP_RETURN_ON_ERROR(esp_ble_gatts_app_register(ESP_APP_ID),
                        TAG, "gatts_app_register");
    ESP_RETURN_ON_ERROR(esp_ble_gatt_set_local_mtu(BLE_MTU_SIZE),
                        TAG, "set_local_mtu");

    ESP_LOGI(TAG, "BLE manager initialised, device: %s", BLE_DEVICE_NAME);
    return ESP_OK;
}

esp_err_t ble_manager_deinit(void)
{
    esp_bluedroid_disable();
    esp_bluedroid_deinit();
    esp_bt_controller_disable();
    esp_bt_controller_deinit();
    return ESP_OK;
}

void ble_manager_process(void)
{
    /* Periodic status notification */
    if (s_state == BLE_STATE_CONNECTED && (s_status_ccc & 0x0001)) {
        char buf[64];
        snprintf(buf, sizeof(buf), "{\"heap\":%lu}", esp_get_free_heap_size());
        ble_manager_send_status((uint8_t *)buf, strlen(buf));
    }
}

bool ble_manager_is_connected(void) { return s_state == BLE_STATE_CONNECTED; }
ble_manager_state_t ble_manager_get_state(void) { return s_state; }

esp_err_t ble_manager_send_status(const uint8_t *data, size_t len)
{
    if (s_conn_id == 0xFFFF || s_gatts_if == ESP_GATT_IF_NONE) return ESP_ERR_INVALID_STATE;
    if (len > sizeof(s_status_val)) len = sizeof(s_status_val);
    memcpy(s_status_val, data, len);
    return esp_ble_gatts_send_indicate(s_gatts_if, s_conn_id,
                                       s_handle_table[IDX_STATUS_VAL],
                                       len, (uint8_t *)data, false);
}

esp_err_t ble_manager_notify_ota(const char *msg)
{
    if (!msg) return ESP_ERR_INVALID_ARG;
    size_t len = strnlen(msg, sizeof(s_ota_val));
    memcpy(s_ota_val, msg, len);
    if (s_conn_id == 0xFFFF) return ESP_ERR_INVALID_STATE;
    return esp_ble_gatts_send_indicate(s_gatts_if, s_conn_id,
                                       s_handle_table[IDX_OTA_VAL],
                                       len, (uint8_t *)msg, false);
}

void ble_manager_register_ctrl_callback(ble_ctrl_callback_t cb)
{
    s_ctrl_cb = cb;
}
