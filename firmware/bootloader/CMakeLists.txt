idf_component_register(
    SRCS "bootloader_main.c"
    INCLUDE_DIRS "."
    REQUIRES
        bootloader
        bootloader_support
        log
        soc
        esp_hw_support
        mbedtls
)
