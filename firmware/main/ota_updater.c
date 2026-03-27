/**
 * @file ota_updater.c
 * @brief OTA firmware update via HTTPS using esp_https_ota.
 */

#include "ota_updater.h"
#include "config.h"
#include "error_logger.h"
#include "ble_manager.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_https_ota.h"
#include "esp_http_client.h"

#define TAG "OTA"

static ota_state_t              s_state    = OTA_STATE_IDLE;
static ota_progress_callback_t  s_prog_cb  = NULL;

static void notify_progress(ota_state_t state, int pct)
{
    s_state = state;
    char msg[64];
    snprintf(msg, sizeof(msg), "{\"ota_state\":%d,\"progress\":%d}", state, pct);
    ble_manager_notify_ota(msg);
    if (s_prog_cb) s_prog_cb(state, pct);
}

esp_err_t ota_updater_init(void)
{
    const esp_partition_t *running = esp_ota_get_running_partition();
    ESP_LOGI(TAG, "Running partition: %s (offset 0x%08lx)",
             running->label, running->address);
    return ESP_OK;
}

esp_err_t ota_updater_run(void)
{
    return ota_updater_run_from_url(OTA_UPDATE_URL);
}

esp_err_t ota_updater_run_from_url(const char *url)
{
    if (!url) return ESP_ERR_INVALID_ARG;
    ESP_LOGI(TAG, "OTA update from: %s", url);
    notify_progress(OTA_STATE_CHECKING, 0);

    esp_http_client_config_t http_cfg = {
        .url             = url,
        .cert_pem        = OTA_SERVER_CERT_PEM,
        .timeout_ms      = OTA_RECV_TIMEOUT_MS,
        .keep_alive_enable = true,
        .buffer_size     = OTA_BUFFER_SIZE,
    };

    esp_https_ota_config_t ota_cfg = {
        .http_config          = &http_cfg,
        .http_client_init_cb  = NULL,
        .bulk_flash_erase     = false,
        .partial_http_download = false,
    };

    esp_https_ota_handle_t handle = NULL;
    notify_progress(OTA_STATE_DOWNLOADING, 0);

    ESP_RETURN_ON_ERROR(esp_https_ota_begin(&ota_cfg, &handle),
                        TAG, "ota_begin failed");

    esp_app_desc_t app_desc;
    if (esp_https_ota_get_img_desc(handle, &app_desc) == ESP_OK) {
        ESP_LOGI(TAG, "New firmware: %s", app_desc.version);
    }

    int img_size  = esp_https_ota_get_image_size(handle);
    int bytes_read = 0;

    while (true) {
        esp_err_t ota_ret = esp_https_ota_perform(handle);
        if (ota_ret == ESP_ERR_HTTPS_OTA_IN_PROGRESS) {
            bytes_read = esp_https_ota_get_image_len_read(handle);
            int pct = (img_size > 0) ? (bytes_read * 100 / img_size) : 0;
            notify_progress(OTA_STATE_DOWNLOADING, pct);
            continue;
        }
        if (ota_ret == ESP_OK) break;
        ESP_LOGE(TAG, "ota_perform error: %s", esp_err_to_name(ota_ret));
        esp_https_ota_abort(handle);
        notify_progress(OTA_STATE_FAILED, 0);
        error_logger_write(ERR_SRC_OTA, ota_ret, "ota_perform failed");
        return ota_ret;
    }

    notify_progress(OTA_STATE_VERIFYING, 95);

    if (!esp_https_ota_is_complete_data_received(handle)) {
        ESP_LOGE(TAG, "Incomplete data received");
        esp_https_ota_abort(handle);
        notify_progress(OTA_STATE_FAILED, 0);
        return ESP_FAIL;
    }

    notify_progress(OTA_STATE_APPLYING, 98);
    esp_err_t finish_ret = esp_https_ota_finish(handle);
    if (finish_ret != ESP_OK) {
        ESP_LOGE(TAG, "ota_finish failed: %s", esp_err_to_name(finish_ret));
        notify_progress(OTA_STATE_FAILED, 0);
        error_logger_write(ERR_SRC_OTA, finish_ret, "ota_finish failed");
        return finish_ret;
    }

    notify_progress(OTA_STATE_SUCCESS, 100);
    ESP_LOGI(TAG, "OTA successful – restarting in 3 s");
    vTaskDelay(pdMS_TO_TICKS(3000));
    esp_restart();
    return ESP_OK;
}

ota_state_t ota_updater_get_state(void) { return s_state; }

void ota_updater_register_progress_cb(ota_progress_callback_t cb) { s_prog_cb = cb; }

const char *ota_updater_get_running_version(void)
{
    const esp_app_desc_t *desc = esp_app_get_description();
    return desc ? desc->version : "unknown";
}
