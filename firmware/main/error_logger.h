#ifndef ERROR_LOGGER_H
#define ERROR_LOGGER_H

#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ERR_SRC_WIFI  = 0,
    ERR_SRC_BLE   = 1,
    ERR_SRC_IOT   = 2,
    ERR_SRC_OTA   = 3,
    ERR_SRC_POWER = 4,
    ERR_SRC_USER  = 5,
} error_source_t;

typedef struct {
    uint32_t       timestamp;
    error_source_t source;
    esp_err_t      code;
    char           message[96];
} error_entry_t;

esp_err_t error_logger_init(void);
esp_err_t error_logger_write(error_source_t src, esp_err_t code, const char *msg);
esp_err_t error_logger_read(uint16_t index, error_entry_t *entry);
esp_err_t error_logger_clear(void);
uint16_t  error_logger_count(void);
void      error_logger_flush(void);

#ifdef __cplusplus
}
#endif
#endif /* ERROR_LOGGER_H */
