package com.offsec.nethunter.utils;

/**
 * NethunterPaths - Central constants class for all file-system paths used by NetHunterZ.
 *
 * <p>All paths are defined as public static final String constants so that they can be
 * referenced throughout the codebase without hard-coding strings. Modify these constants
 * when the on-device layout changes rather than hunting down every usage site.</p>
 */
public final class NethunterPaths {

    /** Prevent instantiation of this constants class. */
    private NethunterPaths() {}

    // -------------------------------------------------------------------------
    // Chroot / system root
    // -------------------------------------------------------------------------

    /** Absolute path to the NetHunter system directory on device storage. */
    public static final String NH_SYSTEM_PATH   = "/data/local/nhsystem";

    /** Absolute path to the root of the Kali Linux chroot environment (arm64). */
    public static final String CHROOT_PATH      = NH_SYSTEM_PATH + "/kali-arm64";

    /** Absolute path to the arm (32-bit) chroot, used on some older devices. */
    public static final String CHROOT_PATH_ARM  = NH_SYSTEM_PATH + "/kali-armhf";

    // -------------------------------------------------------------------------
    // Scripts
    // -------------------------------------------------------------------------

    /** Directory on the device where NetHunter helper scripts are stored. */
    public static final String SCRIPTS_PATH     = "/data/local/nhsystem/scripts";

    /** Path to the bootkali script that mounts and enters the chroot. */
    public static final String BOOTKALI_SCRIPT  = SCRIPTS_PATH + "/bootkali";

    /** Path to the service-check script. */
    public static final String CHECK_SERVICES   = SCRIPTS_PATH + "/check_services.sh";

    // -------------------------------------------------------------------------
    // NetHunter files (configs, modules, duckscripts)
    // -------------------------------------------------------------------------

    /** Root directory for miscellaneous NetHunter data files. */
    public static final String NH_FILES_PATH    = "/data/local/nhsystem/nh_files";

    /** Directory containing network configuration files (e.g., wlan.conf). */
    public static final String CONFIGS_PATH     = NH_FILES_PATH + "/configs";

    /** WLAN configuration file used for monitoring-mode setup. */
    public static final String WLAN_CONF        = CONFIGS_PATH + "/wlan.conf";

    /** Directory containing USB Rubber Ducky / HID duckscripts. */
    public static final String DUCKSCRIPTS_PATH = NH_FILES_PATH + "/duckscripts";

    /** Directory containing kernel modules and Python HID helpers. */
    public static final String MODULES_PATH     = NH_FILES_PATH + "/modules";

    // -------------------------------------------------------------------------
    // GPS
    // -------------------------------------------------------------------------

    /** Path to the NMEA data FIFO / socket used to feed GPS data into the chroot. */
    public static final String GPS_SOCKET_PATH  = "/data/local/nhsystem/nmea_socket";

    // -------------------------------------------------------------------------
    // Init.d
    // -------------------------------------------------------------------------

    /** Init.d directory inside the chroot for startup scripts. */
    public static final String INITD_PATH       = CHROOT_PATH + "/etc/init.d";

    /** NetHunter-specific init.d script (99nethunter). */
    public static final String NH_INITD_SCRIPT  = INITD_PATH + "/99nethunter";

    // -------------------------------------------------------------------------
    // Logs
    // -------------------------------------------------------------------------

    /** Path to the NetHunter application log file. */
    public static final String LOG_PATH         = "/data/local/nhsystem/logs/nethunter.log";
}
