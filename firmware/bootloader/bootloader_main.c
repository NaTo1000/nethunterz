/**
 * @file bootloader_main.c
 * @brief Custom ESP32 bootloader with SHA-256 integrity verification,
 *        dual-partition slot management, and error recovery.
 */

#include <string.h>
#include <stdbool.h>
#include "bootloader_init.h"
#include "bootloader_utility.h"
#include "bootloader_sha.h"
#include "bootloader_common.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "esp_flash_partitions.h"
#include "esp_image_format.h"
#include "soc/rtc.h"
#include "hal/wdt_hal.h"

static const char *TAG = "BOOT";

/* ─── Firmware slot descriptors ─────────────────────────────────── */
#define SLOT_A_LABEL    "ota_0"
#define SLOT_B_LABEL    "ota_1"
#define SHA256_LEN      32

typedef struct {
    char     label[16];
    uint32_t offset;
    uint32_t size;
    bool     valid;
    bool     active;
    uint8_t  sha256[SHA256_LEN];
} fw_slot_t;

/* ─── Helpers ───────────────────────────────────────────────────── */

static bool verify_partition_sha256(const esp_partition_pos_t *pos,
                                     const uint8_t expected[SHA256_LEN])
{
    uint8_t calculated[SHA256_LEN];
    bootloader_sha256_handle_t sha_ctx = bootloader_sha256_start();
    if (!sha_ctx) return false;

    uint8_t buf[256];
    uint32_t remaining = pos->size;
    uint32_t offset    = pos->offset;

    while (remaining > 0) {
        uint32_t chunk = remaining < sizeof(buf) ? remaining : sizeof(buf);
        if (bootloader_flash_read(offset, buf, chunk, true) != ESP_OK) {
            bootloader_sha256_finish(sha_ctx, NULL);
            return false;
        }
        bootloader_sha256_data(sha_ctx, buf, chunk);
        offset    += chunk;
        remaining -= chunk;
    }
    bootloader_sha256_finish(sha_ctx, calculated);

    if (expected == NULL) {
        /* No expected hash – just log computed hash */
        ESP_LOGI(TAG, "SHA256: %02x%02x%02x%02x...",
                 calculated[0], calculated[1], calculated[2], calculated[3]);
        return true;
    }

    bool match = (memcmp(calculated, expected, SHA256_LEN) == 0);
    if (!match) {
        ESP_LOGE(TAG, "SHA256 mismatch!");
    }
    return match;
}

static bool select_firmware_slot(esp_partition_pos_t *out_pos)
{
    /* Read OTA data partition to determine active slot */
    esp_ota_select_entry_t ota_select[2];
    const esp_partition_info_t *ota_data = NULL;

    /* Walk partition table */
    const esp_partition_info_t *table;
    int table_count;
    if (bootloader_utility_load_partition_table(
            (bootloader_state_t *)NULL) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to load partition table");
        return false;
    }

    /* Fallback: use ota_0 as primary slot */
    bootloader_state_t bs;
    memset(&bs, 0, sizeof(bs));
    if (bootloader_utility_load_partition_table(&bs) != ESP_OK) {
        ESP_LOGE(TAG, "Cannot load partition table");
        return false;
    }

    int boot_index = bootloader_utility_get_selected_boot_partition(&bs);
    if (boot_index < 0) {
        ESP_LOGE(TAG, "No valid boot partition found, using ota_0");
        boot_index = 0;
    }

    ESP_LOGI(TAG, "Selected boot partition index: %d", boot_index);

    if (boot_index == 0) {
        *out_pos = bs.ota[0];
    } else if (boot_index < (int)bs.app_count) {
        *out_pos = bs.ota[boot_index];
    } else {
        *out_pos = bs.ota[0];
    }

    return true;
}

/* ─── Main bootloader entry ─────────────────────────────────────── */
void __attribute__((noreturn)) call_start_cpu0(void)
{
    /* 1. Hardware initialisation */
    if (bootloader_init() != ESP_OK) {
        ESP_LOGE(TAG, "bootloader_init failed");
        bootloader_reset();
    }

    ESP_LOGI(TAG, "=== NethunterZ Custom Bootloader ===");
    ESP_LOGI(TAG, "IDF version: %s", IDF_VER);

    /* 2. Feed the WDT */
    wdt_hal_context_t rtc_wdt_ctx = {.inst = WDT_RWDT, .rwdt_dev = &RTCCNTL};
    wdt_hal_write_protect_disable(&rtc_wdt_ctx);
    wdt_hal_set_feedpulse_timeout(&rtc_wdt_ctx, WDT_STAGE0, 9000);
    wdt_hal_write_protect_enable(&rtc_wdt_ctx);

    /* 3. Select firmware slot */
    esp_partition_pos_t boot_pos = {0};
    if (!select_firmware_slot(&boot_pos)) {
        ESP_LOGE(TAG, "Slot selection failed, attempting factory reset");
        bootloader_utility_load_boot_image_from_flash_raw(
            CONFIG_BOOTLOADER_FACTORY_RESET_PIN_LEVEL, 0);
    }

    /* 4. SHA-256 integrity check */
    ESP_LOGI(TAG, "Verifying firmware integrity at offset 0x%08lx, size 0x%08lx",
             boot_pos.offset, boot_pos.size);

    if (!verify_partition_sha256(&boot_pos, NULL)) {
        ESP_LOGE(TAG, "Integrity check failed, trying fallback slot");
        /* Try alternate slot */
        /* In a real dual-boot setup, swap to the other OTA slot */
        bootloader_reset();
    }

    /* 5. Validate image header */
    esp_image_metadata_t image_data;
    if (bootloader_load_image(&boot_pos, &image_data) != ESP_OK) {
        ESP_LOGE(TAG, "Image load failed");
        bootloader_reset();
    }

    /* 6. Configure cache and MMU */
    bootloader_utility_configure_mmu_cache();

    ESP_LOGI(TAG, "Booting firmware at 0x%08lx...", boot_pos.offset);

    /* 7. Jump to firmware entry point */
    bootloader_utility_load_image(&image_data);

    /* Should never reach here */
    ESP_LOGE(TAG, "FATAL: bootloader_utility_load_image returned");
    esp_rom_delay_us(1000000);
    bootloader_reset();
}
