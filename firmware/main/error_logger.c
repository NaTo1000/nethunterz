/**
 * @file error_logger.c
 * @brief Flash-based error logging with NVS ring buffer.
 */

#include "error_logger.h"
#include "config.h"

#include <string.h>
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "nvs_flash.h"

#define TAG "ERR_LOG"

static SemaphoreHandle_t s_mutex      = NULL;
static uint16_t          s_head       = 0;
static uint16_t          s_count      = 0;
static bool              s_initialized= false;

/* ─── Persistent head/count in NVS ─────────────────────────────── */
static void load_indices(void)
{
    nvs_handle_t nvs;
    if (nvs_open(ERR_LOG_NVS_NAMESPACE, NVS_READONLY, &nvs) != ESP_OK) return;
    nvs_get_u16(nvs, "head",  &s_head);
    nvs_get_u16(nvs, "count", &s_count);
    nvs_close(nvs);
}

static void save_indices(void)
{
    nvs_handle_t nvs;
    if (nvs_open(ERR_LOG_NVS_NAMESPACE, NVS_READWRITE, &nvs) != ESP_OK) return;
    nvs_set_u16(nvs, "head",  s_head);
    nvs_set_u16(nvs, "count", s_count);
    nvs_commit(nvs);
    nvs_close(nvs);
}

esp_err_t error_logger_init(void)
{
    if (s_initialized) return ESP_OK;
    s_mutex = xSemaphoreCreateMutex();
    if (!s_mutex) return ESP_ERR_NO_MEM;
    load_indices();
    s_initialized = true;
    ESP_LOGI(TAG, "Error logger initialised: %u entries in ring buffer", s_count);
    return ESP_OK;
}

esp_err_t error_logger_write(error_source_t src, esp_err_t code, const char *msg)
{
    if (!s_initialized) return ESP_ERR_INVALID_STATE;
    if (xSemaphoreTake(s_mutex, pdMS_TO_TICKS(100)) != pdTRUE) return ESP_ERR_TIMEOUT;

    error_entry_t entry = {
        .timestamp = (uint32_t)(esp_timer_get_time() / 1000000ULL),
        .source    = src,
        .code      = code,
    };
    if (msg) strlcpy(entry.message, msg, sizeof(entry.message));

    char key[16];
    snprintf(key, sizeof(key), ERR_LOG_ENTRY_KEY_FMT, s_head);

    nvs_handle_t nvs;
    esp_err_t ret = nvs_open(ERR_LOG_NVS_NAMESPACE, NVS_READWRITE, &nvs);
    if (ret == ESP_OK) {
        nvs_set_blob(nvs, key, &entry, sizeof(entry));
        nvs_commit(nvs);
        nvs_close(nvs);
    }

    s_head = (s_head + 1) % ERR_LOG_MAX_ENTRIES;
    if (s_count < ERR_LOG_MAX_ENTRIES) s_count++;
    save_indices();

    ESP_LOGW(TAG, "[%lu] src=%d code=0x%x msg=%s",
             entry.timestamp, src, code, entry.message);

    xSemaphoreGive(s_mutex);
    return ESP_OK;
}

esp_err_t error_logger_read(uint16_t index, error_entry_t *entry)
{
    if (!entry || index >= s_count) return ESP_ERR_INVALID_ARG;
    char key[16];
    uint16_t real_idx = (s_head - s_count + index + ERR_LOG_MAX_ENTRIES)
                        % ERR_LOG_MAX_ENTRIES;
    snprintf(key, sizeof(key), ERR_LOG_ENTRY_KEY_FMT, real_idx);

    nvs_handle_t nvs;
    esp_err_t ret = nvs_open(ERR_LOG_NVS_NAMESPACE, NVS_READONLY, &nvs);
    if (ret != ESP_OK) return ret;
    size_t len = sizeof(*entry);
    ret = nvs_get_blob(nvs, key, entry, &len);
    nvs_close(nvs);
    return ret;
}

esp_err_t error_logger_clear(void)
{
    nvs_handle_t nvs;
    esp_err_t ret = nvs_open(ERR_LOG_NVS_NAMESPACE, NVS_READWRITE, &nvs);
    if (ret != ESP_OK) return ret;
    nvs_erase_all(nvs);
    nvs_commit(nvs);
    nvs_close(nvs);
    s_head = 0; s_count = 0;
    return ESP_OK;
}

uint16_t error_logger_count(void) { return s_count; }

void error_logger_flush(void)
{
    /* In a more complex implementation, flush to remote server */
    ESP_LOGD(TAG, "Flush: %u error entries persisted", s_count);
}
