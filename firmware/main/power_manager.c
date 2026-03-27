/**
 * @file power_manager.c
 * @brief Deep sleep, light sleep, and dynamic frequency scaling.
 */

#include "power_manager.h"
#include "config.h"
#include "error_logger.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_pm.h"
#include "driver/adc.h"
#include "esp_adc_cal.h"

#define TAG "PWR_MGR"

static power_mode_t s_mode = POWER_MODE_ACTIVE;
static esp_adc_cal_characteristics_t s_adc_chars;
static bool s_adc_calibrated = false;
static uint32_t s_battery_mv = 0;
static uint32_t s_idle_ticks = 0;

#define IDLE_TICKS_FOR_LIGHT_SLEEP  300   /* ~5 min */
#define IDLE_TICKS_FOR_DEEP_SLEEP   1800  /* ~30 min */

esp_err_t power_manager_init(void)
{
    /* Configure ADC for battery voltage */
    esp_adc_cal_value_t cal_type =
        esp_adc_cal_characterize(ADC_UNIT_1, ADC_ATTEN_DB_11,
                                 ADC_WIDTH_BIT_12, 1100, &s_adc_chars);
    s_adc_calibrated = (cal_type != ESP_ADC_CAL_VAL_NOT_SUPPORTED);

    /* Enable sleep wakeup sources */
    esp_sleep_enable_timer_wakeup(DEEP_SLEEP_DURATION_US);
    esp_sleep_enable_gpio_wakeup();

    /* Configure PM for dynamic frequency scaling */
#if CONFIG_PM_ENABLE
    esp_pm_config_t pm_cfg = {
        .max_freq_mhz       = CPU_FREQ_HIGH_MHZ,
        .min_freq_mhz       = CPU_FREQ_LOW_MHZ,
        .light_sleep_enable = true,
    };
    esp_pm_configure(&pm_cfg);
#endif

    ESP_LOGI(TAG, "Power manager initialised (ADC cal: %s)",
             s_adc_calibrated ? "yes" : "no");
    return ESP_OK;
}

void power_manager_process(void)
{
    /* Read battery voltage */
    uint32_t raw = adc1_get_raw(BATTERY_ADC_CHANNEL);
    if (s_adc_calibrated) {
        s_battery_mv = esp_adc_cal_raw_to_voltage(raw, &s_adc_chars) * 2;
    } else {
        s_battery_mv = (raw * 3300 / 4096) * 2;
    }

    if (s_battery_mv < BATTERY_CRITICAL_MV) {
        ESP_LOGW(TAG, "Battery critical: %lu mV – entering deep sleep", s_battery_mv);
        error_logger_write(ERR_SRC_POWER, ESP_ERR_INVALID_STATE, "Battery critical");
        power_manager_enter_deep_sleep(DEEP_SLEEP_DURATION_US);
    } else if (s_battery_mv < BATTERY_LOW_MV) {
        ESP_LOGW(TAG, "Battery low: %lu mV", s_battery_mv);
        power_manager_set_cpu_freq(CPU_FREQ_LOW_MHZ);
    }

    s_idle_ticks++;
}

esp_err_t power_manager_set_mode(power_mode_t mode)
{
    s_mode = mode;
    ESP_LOGI(TAG, "Power mode → %d", mode);
    switch (mode) {
    case POWER_MODE_LIGHT_SLEEP:
        return power_manager_enter_light_sleep(LIGHT_SLEEP_DURATION_US);
    case POWER_MODE_DEEP_SLEEP:
        return power_manager_enter_deep_sleep(DEEP_SLEEP_DURATION_US);
    default:
        break;
    }
    return ESP_OK;
}

power_mode_t power_manager_get_mode(void) { return s_mode; }

esp_err_t power_manager_enter_light_sleep(uint64_t duration_us)
{
    ESP_LOGI(TAG, "Entering light sleep for %llu us", duration_us);
    esp_sleep_enable_timer_wakeup(duration_us);
    esp_light_sleep_start();
    ESP_LOGI(TAG, "Woke from light sleep");
    s_mode = POWER_MODE_ACTIVE;
    return ESP_OK;
}

esp_err_t power_manager_enter_deep_sleep(uint64_t duration_us)
{
    ESP_LOGI(TAG, "Entering deep sleep for %llu us", duration_us);
    esp_sleep_enable_timer_wakeup(duration_us);
    esp_deep_sleep_start();
    /* Never returns */
    return ESP_OK;
}

uint32_t power_manager_get_battery_mv(void) { return s_battery_mv; }

bool power_manager_is_battery_low(void)
{
    return s_battery_mv > 0 && s_battery_mv < BATTERY_LOW_MV;
}

esp_err_t power_manager_set_cpu_freq(uint32_t freq_mhz)
{
#if CONFIG_PM_ENABLE
    esp_pm_config_t cfg = {
        .max_freq_mhz       = freq_mhz,
        .min_freq_mhz       = CPU_FREQ_LOW_MHZ,
        .light_sleep_enable = true,
    };
    return esp_pm_configure(&cfg);
#else
    return ESP_ERR_NOT_SUPPORTED;
#endif
}
