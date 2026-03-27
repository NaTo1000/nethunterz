#ifndef OTA_UPDATER_H
#define OTA_UPDATER_H

#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    OTA_STATE_IDLE       = 0,
    OTA_STATE_CHECKING   = 1,
    OTA_STATE_DOWNLOADING= 2,
    OTA_STATE_VERIFYING  = 3,
    OTA_STATE_APPLYING   = 4,
    OTA_STATE_SUCCESS    = 5,
    OTA_STATE_FAILED     = 6,
} ota_state_t;

typedef void (*ota_progress_callback_t)(ota_state_t state, int progress_pct);

esp_err_t   ota_updater_init(void);
esp_err_t   ota_updater_run(void);
esp_err_t   ota_updater_run_from_url(const char *url);
ota_state_t ota_updater_get_state(void);
void        ota_updater_register_progress_cb(ota_progress_callback_t cb);
const char *ota_updater_get_running_version(void);

#ifdef __cplusplus
}
#endif
#endif /* OTA_UPDATER_H */
