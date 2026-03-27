/**
 * @file main.c
 * @brief NethunterZ ESP32 Firmware – Main Entry Point
 *
 * Creates and coordinates FreeRTOS tasks for:
 *   - WiFi station/AP management
 *   - BLE GATT server
 *   - IoT/MQTT cloud communication
 *   - OTA firmware updates
 *   - Power management (deep/light sleep + DVFS)
 *   - Flash-based error logging
 */

#include <stdio.h>
#include <string.h>
#include <stdbool.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"

#include "esp_system.h"
#include "esp_log.h"
#include "esp_err.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "driver/gpio.h"
#include "driver/adc.h"

#include "config.h"
#include "wifi_manager.h"
#include "ble_manager.h"
#include "iot_manager.h"
#include "power_manager.h"
#include "error_logger.h"
#include "ota_updater.h"

static const char *TAG = "MAIN";

/* ─── Global Event Group ────────────────────────────────────────── */
EventGroupHandle_t g_system_events;

/* ─── Global Queue for inter-task messages ──────────────────────── */
QueueHandle_t g_cmd_queue;

/* ─── Mutex protecting shared NVS access ───────────────────────── */
SemaphoreHandle_t g_nvs_mutex;

/* ─── Task handles ──────────────────────────────────────────────── */
static TaskHandle_t s_wifi_task_handle     = NULL;
static TaskHandle_t s_ble_task_handle      = NULL;
static TaskHandle_t s_iot_task_handle      = NULL;
static TaskHandle_t s_power_task_handle    = NULL;
static TaskHandle_t s_ota_task_handle      = NULL;
static TaskHandle_t s_errlog_task_handle   = NULL;

/* ─── Boot counter (persisted in NVS) ──────────────────────────── */
static uint32_t s_boot_count = 0;

/* ─── Forward declarations ──────────────────────────────────────── */
static esp_err_t nvs_init(void);
static esp_err_t hardware_init(void);
static esp_err_t load_boot_count(void);
static void      blink_status_led(uint8_t times);

/* ─── WiFi task ─────────────────────────────────────────────────── */
static void wifi_task(void *pvParams)
{
    ESP_LOGI(TAG, "wifi_task started");
    esp_err_t ret = wifi_manager_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "wifi_manager_init failed: %s", esp_err_to_name(ret));
        error_logger_write(ERR_SRC_WIFI, ret, "wifi_manager_init failed");
    }

    for (;;) {
        wifi_manager_process();
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

/* ─── BLE task ──────────────────────────────────────────────────── */
static void ble_task(void *pvParams)
{
    ESP_LOGI(TAG, "ble_task started");
    esp_err_t ret = ble_manager_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "ble_manager_init failed: %s", esp_err_to_name(ret));
        error_logger_write(ERR_SRC_BLE, ret, "ble_manager_init failed");
    }

    for (;;) {
        ble_manager_process();
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

/* ─── IoT/MQTT task ─────────────────────────────────────────────── */
static void iot_task(void *pvParams)
{
    ESP_LOGI(TAG, "iot_task started");

    /* Wait until WiFi is connected before starting MQTT */
    xEventGroupWaitBits(g_system_events, NOTIF_WIFI_CONNECTED,
                        pdFALSE, pdTRUE, portMAX_DELAY);

    esp_err_t ret = iot_manager_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "iot_manager_init failed: %s", esp_err_to_name(ret));
        error_logger_write(ERR_SRC_IOT, ret, "iot_manager_init failed");
    }

    for (;;) {
        iot_manager_process();
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

/* ─── Power management task ─────────────────────────────────────── */
static void power_task(void *pvParams)
{
    ESP_LOGI(TAG, "power_task started");
    esp_err_t ret = power_manager_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "power_manager_init failed: %s", esp_err_to_name(ret));
        error_logger_write(ERR_SRC_POWER, ret, "power_manager_init failed");
    }

    for (;;) {
        power_manager_process();
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

/* ─── OTA updater task ──────────────────────────────────────────── */
static void ota_task(void *pvParams)
{
    ESP_LOGI(TAG, "ota_task started");
    esp_err_t ret = ota_updater_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "ota_updater_init failed: %s", esp_err_to_name(ret));
    }

    for (;;) {
        /* Block until an OTA trigger notification arrives */
        uint32_t notif = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (notif > 0) {
            ESP_LOGI(TAG, "OTA trigger received, starting update...");
            ret = ota_updater_run();
            if (ret != ESP_OK) {
                ESP_LOGE(TAG, "OTA update failed: %s", esp_err_to_name(ret));
                error_logger_write(ERR_SRC_OTA, ret, "OTA update failed");
            }
        }
    }
}

/* ─── Error logger task ─────────────────────────────────────────── */
static void error_log_task(void *pvParams)
{
    ESP_LOGI(TAG, "error_log_task started");
    esp_err_t ret = error_logger_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "error_logger_init failed: %s", esp_err_to_name(ret));
    }

    for (;;) {
        error_logger_flush();
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

/* ─── NVS Initialisation ────────────────────────────────────────── */
static esp_err_t nvs_init(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS partition erased, re-initialising");
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    return ret;
}

/* ─── Hardware Initialisation ───────────────────────────────────── */
static esp_err_t hardware_init(void)
{
    /* Status LED */
    gpio_config_t led_cfg = {
        .pin_bit_mask = (1ULL << PIN_STATUS_LED),
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    gpio_config(&led_cfg);
    gpio_set_level(PIN_STATUS_LED, 0);

    /* Boot button */
    gpio_config_t btn_cfg = {
        .pin_bit_mask = (1ULL << PIN_BOOT_BTN),
        .mode         = GPIO_MODE_INPUT,
        .pull_up_en   = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    gpio_config(&btn_cfg);

    /* ADC for battery voltage */
    adc1_config_width(ADC_WIDTH_BIT_12);
    adc1_config_channel_atten(BATTERY_ADC_CHANNEL, ADC_ATTEN_DB_11);

    return ESP_OK;
}

/* ─── Boot counter ──────────────────────────────────────────────── */
static esp_err_t load_boot_count(void)
{
    nvs_handle_t nvs;
    esp_err_t ret = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs);
    if (ret != ESP_OK) return ret;

    nvs_get_u32(nvs, NVS_KEY_BOOT_COUNT, &s_boot_count);
    s_boot_count++;
    ret = nvs_set_u32(nvs, NVS_KEY_BOOT_COUNT, s_boot_count);
    nvs_commit(nvs);
    nvs_close(nvs);
    return ret;
}

/* ─── Status LED blink helper ───────────────────────────────────── */
static void blink_status_led(uint8_t times)
{
    for (uint8_t i = 0; i < times; i++) {
        gpio_set_level(PIN_STATUS_LED, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level(PIN_STATUS_LED, 0);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

/* ─── app_main ──────────────────────────────────────────────────── */
void app_main(void)
{
    ESP_LOGI(TAG, "=== NethunterZ ESP32 Firmware v%s ===", FW_VERSION_STRING);
    ESP_LOGI(TAG, "Build: %s %s", FW_BUILD_DATE, FW_BUILD_TIME);
    ESP_LOGI(TAG, "Chip: %s  Rev: %d  Cores: %d",
             CONFIG_IDF_TARGET,
             esp_efuse_get_chip_ver(),
             portNUM_PROCESSORS);

    /* ── Core system init ── */
    ESP_ERROR_CHECK(nvs_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(hardware_init());
    load_boot_count();

    ESP_LOGI(TAG, "Boot count: %lu", s_boot_count);

    /* ── Create synchronisation primitives ── */
    g_system_events = xEventGroupCreate();
    configASSERT(g_system_events);

    g_cmd_queue = xQueueCreate(16, sizeof(uint32_t));
    configASSERT(g_cmd_queue);

    g_nvs_mutex = xSemaphoreCreateMutex();
    configASSERT(g_nvs_mutex);

    /* ── Indicate startup ── */
    blink_status_led(3);

    /* ── Create all FreeRTOS tasks ── */
    BaseType_t rc;

    rc = xTaskCreatePinnedToCore(error_log_task, "errlog_task",
                                 ERR_LOG_TASK_STACK, NULL,
                                 ERR_LOG_TASK_PRIORITY,
                                 &s_errlog_task_handle, APP_CPU_NUM);
    configASSERT(rc == pdPASS);

    rc = xTaskCreatePinnedToCore(wifi_task, "wifi_task",
                                 WIFI_TASK_STACK, NULL,
                                 WIFI_TASK_PRIORITY,
                                 &s_wifi_task_handle, PRO_CPU_NUM);
    configASSERT(rc == pdPASS);

    rc = xTaskCreatePinnedToCore(ble_task, "ble_task",
                                 BLE_TASK_STACK, NULL,
                                 BLE_TASK_PRIORITY,
                                 &s_ble_task_handle, APP_CPU_NUM);
    configASSERT(rc == pdPASS);

    rc = xTaskCreatePinnedToCore(iot_task, "iot_task",
                                 IOT_TASK_STACK, NULL,
                                 IOT_TASK_PRIORITY,
                                 &s_iot_task_handle, APP_CPU_NUM);
    configASSERT(rc == pdPASS);

    rc = xTaskCreatePinnedToCore(power_task, "power_task",
                                 POWER_TASK_STACK, NULL,
                                 POWER_TASK_PRIORITY,
                                 &s_power_task_handle, APP_CPU_NUM);
    configASSERT(rc == pdPASS);

    rc = xTaskCreatePinnedToCore(ota_task, "ota_task",
                                 OTA_TASK_STACK, NULL,
                                 OTA_TASK_PRIORITY,
                                 &s_ota_task_handle, APP_CPU_NUM);
    configASSERT(rc == pdPASS);

    ESP_LOGI(TAG, "All tasks created successfully");

    /* ── Main loop: watchdog / diagnostics ── */
    for (;;) {
        ESP_LOGD(TAG, "Heap free: %lu bytes  Min free: %lu bytes",
                 esp_get_free_heap_size(),
                 esp_get_minimum_free_heap_size());

        /* Toggle status LED to show main loop is alive */
        gpio_set_level(PIN_STATUS_LED, 1);
        vTaskDelay(pdMS_TO_TICKS(50));
        gpio_set_level(PIN_STATUS_LED, 0);

        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}
