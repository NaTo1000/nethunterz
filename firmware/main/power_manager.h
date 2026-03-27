#ifndef POWER_MANAGER_H
#define POWER_MANAGER_H

#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    POWER_MODE_ACTIVE        = 0,
    POWER_MODE_LIGHT_SLEEP   = 1,
    POWER_MODE_DEEP_SLEEP    = 2,
    POWER_MODE_MODEM_SLEEP   = 3,
} power_mode_t;

esp_err_t   power_manager_init(void);
void        power_manager_process(void);
esp_err_t   power_manager_set_mode(power_mode_t mode);
power_mode_t power_manager_get_mode(void);
esp_err_t   power_manager_enter_light_sleep(uint64_t duration_us);
esp_err_t   power_manager_enter_deep_sleep(uint64_t duration_us);
uint32_t    power_manager_get_battery_mv(void);
bool        power_manager_is_battery_low(void);
esp_err_t   power_manager_set_cpu_freq(uint32_t freq_mhz);

#ifdef __cplusplus
}
#endif
#endif /* POWER_MANAGER_H */
