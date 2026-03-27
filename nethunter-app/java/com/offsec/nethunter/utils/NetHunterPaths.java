package com.offsec.nethunter.utils;

import android.content.Context;

import androidx.annotation.NonNull;

import java.io.File;

/**
 * Central registry of all file-system paths used by NetHunter.
 *
 * <p>The chroot root path is architecture-dependent:
 * <ul>
 *   <li>64-bit devices use {@code /data/local/nhsystem/kali-arm64}</li>
 *   <li>32-bit devices use {@code /data/local/nhsystem/kali-armhf}</li>
 *   <li>x86_64 devices use {@code /data/local/nhsystem/kali-amd64}</li>
 *   <li>x86 devices use {@code /data/local/nhsystem/kali-i386}</li>
 * </ul>
 *
 * <p>All path constants are {@code static final}. Dynamic paths (those that
 * depend on the architecture or application context) are resolved via static
 * methods.
 */
public final class NetHunterPaths {

    // -------------------------------------------------------------------------
    // Root paths
    // -------------------------------------------------------------------------

    /** Base directory for all NetHunter data on the device. */
    public static final String NH_SYSTEM_ROOT     = "/data/local/nhsystem";

    /** Default chroot names per architecture. */
    public static final String CHROOT_ARM64       = NH_SYSTEM_ROOT + "/kali-arm64";
    public static final String CHROOT_ARMHF       = NH_SYSTEM_ROOT + "/kali-armhf";
    public static final String CHROOT_AMD64       = NH_SYSTEM_ROOT + "/kali-amd64";
    public static final String CHROOT_I386        = NH_SYSTEM_ROOT + "/kali-i386";

    // -------------------------------------------------------------------------
    // Chroot-relative paths
    // -------------------------------------------------------------------------

    public static final String CHROOT_ETC         = "/etc";
    public static final String CHROOT_ETC_INITD   = "/etc/init.d";
    public static final String CHROOT_HOME        = "/root";
    public static final String CHROOT_TMP         = "/tmp";
    public static final String CHROOT_USR_BIN     = "/usr/bin";

    // -------------------------------------------------------------------------
    // Application data directories
    // -------------------------------------------------------------------------

    /** Parent directory for extracted NetHunter files in app-internal storage. */
    public static final String APP_DATA_DIR       = "/data/data/com.offsec.nethunter/files";

    /** Scripts extracted from assets. */
    public static final String SCRIPTS_DIR        = APP_DATA_DIR + "/scripts";

    /** NetHunter configuration files. */
    public static final String CONFIGS_DIR        = APP_DATA_DIR + "/nh_files/configs";

    /** DuckHunter/USB-HID payload scripts. */
    public static final String DUCKSCRIPTS_DIR    = APP_DATA_DIR + "/nh_files/duckscripts";

    /** Python modules for HID injection. */
    public static final String MODULES_DIR        = APP_DATA_DIR + "/nh_files/modules";

    /** Log files. */
    public static final String LOGS_DIR           = APP_DATA_DIR + "/logs";

    // -------------------------------------------------------------------------
    // Script paths
    // -------------------------------------------------------------------------

    public static final String BOOTKALI_SCRIPT    = SCRIPTS_DIR + "/bootkali";
    public static final String BOOTKALI_CHECK     = SCRIPTS_DIR + "/bootkali_check";
    public static final String NH_LAUNCHER        = SCRIPTS_DIR + "/nethunter";
    public static final String START_SERVICES_SH  = SCRIPTS_DIR + "/start_services.sh";

    // -------------------------------------------------------------------------
    // Config file paths
    // -------------------------------------------------------------------------

    public static final String WPA_SUPPLICANT_CONF = CONFIGS_DIR + "/wpa_supplicant.conf";
    public static final String RESOLV_CONF         = CONFIGS_DIR + "/resolv.conf";

    // -------------------------------------------------------------------------
    // Log file
    // -------------------------------------------------------------------------

    public static final String LOG_FILE           = LOGS_DIR + "/nethunter.log";

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    private NetHunterPaths() {}

    // -------------------------------------------------------------------------
    // Dynamic path resolution
    // -------------------------------------------------------------------------

    /**
     * Returns the architecture-appropriate chroot root path.
     *
     * @return absolute path to the Kali chroot directory
     */
    @NonNull
    public static String getChrootPath() {
        String abi = SystemUtils.getPrimaryAbi();
        if (abi.startsWith("arm64") || abi.equals("aarch64")) {
            return CHROOT_ARM64;
        } else if (abi.startsWith("x86_64")) {
            return CHROOT_AMD64;
        } else if (abi.startsWith("x86")) {
            return CHROOT_I386;
        } else {
            return CHROOT_ARMHF;
        }
    }

    /**
     * Returns the absolute path to a file inside the chroot.
     *
     * @param relativePath the path relative to the chroot root (must start with {@code /})
     * @return absolute host path, e.g. {@code /data/local/nhsystem/kali-arm64/etc/resolv.conf}
     */
    @NonNull
    public static String inChroot(@NonNull String relativePath) {
        return getChrootPath() + relativePath;
    }

    // -------------------------------------------------------------------------
    // Directory creation
    // -------------------------------------------------------------------------

    /**
     * Creates all application-level directories that are expected to exist at
     * runtime. Logs a warning for any directory that cannot be created.
     *
     * @param context the application context (used for getFilesDir fallback)
     */
    public static void ensureDirectoriesExist(@NonNull Context context) {
        String[] dirs = {
            SCRIPTS_DIR,
            CONFIGS_DIR,
            DUCKSCRIPTS_DIR,
            MODULES_DIR,
            LOGS_DIR
        };
        for (String path : dirs) {
            File dir = new File(path);
            if (!dir.exists() && !dir.mkdirs()) {
                Logger.w("NetHunterPaths", "Could not create directory: " + path);
            }
        }
    }

    // -------------------------------------------------------------------------
    // Validation
    // -------------------------------------------------------------------------

    /**
     * Returns {@code true} if the chroot appears to be installed (the directory
     * exists and is non-empty).
     *
     * @return {@code true} when the chroot root directory is present
     */
    public static boolean isChrootInstalled() {
        File chrootDir = new File(getChrootPath());
        String[] entries = chrootDir.list();
        return chrootDir.exists() && chrootDir.isDirectory()
                && entries != null && entries.length > 0;
    }

    /**
     * Returns {@code true} if {@code path} exists on the file system.
     *
     * @param path absolute file-system path to test
     * @return {@code true} if the path exists
     */
    public static boolean exists(@NonNull String path) {
        return new File(path).exists();
    }
}
