package com.offsec.nethunter.utils;

import android.os.Build;

import androidx.annotation.NonNull;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStreamReader;

/**
 * Utility class providing system-level information relevant to penetration
 * testing and chroot operations on Android devices.
 *
 * <p>All methods are stateless static helpers; no instance is required.
 */
public final class SystemUtils {

    private static final String TAG = "SystemUtils";

    /** Common paths where the {@code su} binary may reside. */
    private static final String[] SU_PATHS = {
        "/system/bin/su",
        "/system/xbin/su",
        "/sbin/su",
        "/su/bin/su",
        "/magisk/.core/bin/su",
        "/data/local/xbin/su",
        "/data/local/bin/su",
        "/data/local/su"
    };

    private SystemUtils() {}

    // -------------------------------------------------------------------------
    // Root detection
    // -------------------------------------------------------------------------

    /**
     * Performs a multi-method root availability check.
     *
     * <p>Strategy (in order):
     * <ol>
     *   <li>Look for a {@code su} binary in common locations.</li>
     *   <li>Execute {@code id} via the located {@code su} and check for
     *       {@code uid=0}.</li>
     *   <li>Check for Magisk / SuperSU app packages.</li>
     * </ol>
     *
     * @return {@code true} if root access appears to be available
     */
    public static boolean isRootAvailable() {
        if (findSuBinary() != null) {
            return canExecuteId();
        }
        return false;
    }

    /**
     * Searches common file-system locations for a {@code su} binary.
     *
     * @return the path to the first found {@code su} binary, or {@code null}
     */
    @Nullable
    public static String findSuBinary() {
        for (String path : SU_PATHS) {
            File f = new File(path);
            if (f.exists() && f.canExecute()) {
                Logger.d(TAG, "Found su at: " + path);
                return path;
            }
        }
        return null;
    }

    /**
     * Attempts to run {@code id} via {@code su} and checks whether the output
     * contains {@code uid=0}.
     *
     * @return {@code true} if root execution succeeded
     */
    public static boolean canExecuteId() {
        try {
            Process proc = Runtime.getRuntime().exec(new String[]{"su", "-c", "id"});
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(proc.getInputStream()))) {
                String line = reader.readLine();
                if (line != null && line.contains("uid=0")) {
                    return true;
                }
            }
            proc.waitFor();
        } catch (IOException | InterruptedException e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
        }
        return false;
    }

    // -------------------------------------------------------------------------
    // Architecture
    // -------------------------------------------------------------------------

    /**
     * Returns the primary ABI of the device, e.g. {@code "arm64-v8a"},
     * {@code "armeabi-v7a"}, or {@code "x86_64"}.
     *
     * @return the primary ABI string
     */
    @NonNull
    public static String getPrimaryAbi() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP
                && Build.SUPPORTED_ABIS.length > 0) {
            return Build.SUPPORTED_ABIS[0];
        }
        return Build.CPU_ABI;
    }

    /**
     * Returns {@code true} if the device runs a 64-bit (arm64 or x86_64) ABI.
     */
    public static boolean is64Bit() {
        String abi = getPrimaryAbi();
        return abi.contains("arm64") || abi.contains("x86_64") || abi.contains("mips64");
    }

    // -------------------------------------------------------------------------
    // Kernel
    // -------------------------------------------------------------------------

    /**
     * Returns the Linux kernel version string from {@code /proc/version}.
     *
     * @return the kernel version line, or {@code "unknown"} on error
     */
    @NonNull
    public static String getKernelVersion() {
        try (BufferedReader reader = new BufferedReader(new FileReader("/proc/version"))) {
            String line = reader.readLine();
            return line != null ? line : "unknown";
        } catch (IOException e) {
            return "unknown";
        }
    }

    // -------------------------------------------------------------------------
    // SELinux
    // -------------------------------------------------------------------------

    /**
     * Returns the current SELinux enforcement mode by reading
     * {@code /sys/fs/selinux/enforce}.
     *
     * @return {@code "Enforcing"}, {@code "Permissive"}, or {@code "Disabled/Unknown"}
     */
    @NonNull
    public static String getSELinuxStatus() {
        File enforce = new File("/sys/fs/selinux/enforce");
        if (!enforce.exists()) return "Disabled/Unknown";
        try (BufferedReader r = new BufferedReader(new FileReader(enforce))) {
            String line = r.readLine();
            if ("1".equals(line)) return "Enforcing";
            if ("0".equals(line)) return "Permissive";
        } catch (IOException e) {
            Logger.w(TAG, "Could not read SELinux status: " + e.getMessage());
        }
        return "Disabled/Unknown";
    }

    // -------------------------------------------------------------------------
    // Memory
    // -------------------------------------------------------------------------

    /**
     * Reads total and available RAM from {@code /proc/meminfo}.
     *
     * @return a two-element array {@code [totalKb, availableKb]}, or
     *         {@code [-1, -1]} on error
     */
    @NonNull
    public static long[] getMemoryInfo() {
        long total = -1;
        long avail = -1;
        try (BufferedReader r = new BufferedReader(new FileReader("/proc/meminfo"))) {
            String line;
            while ((line = r.readLine()) != null) {
                if (line.startsWith("MemTotal:")) {
                    total = parseProcMemLine(line);
                } else if (line.startsWith("MemAvailable:")) {
                    avail = parseProcMemLine(line);
                }
                if (total >= 0 && avail >= 0) break;
            }
        } catch (IOException e) {
            Logger.w(TAG, "Could not read /proc/meminfo: " + e.getMessage());
        }
        return new long[]{total, avail};
    }

    // -------------------------------------------------------------------------
    // CPU
    // -------------------------------------------------------------------------

    /**
     * Returns the number of CPU cores available to the runtime.
     *
     * @return number of logical CPU cores (≥ 1)
     */
    public static int getCpuCoreCount() {
        return Runtime.getRuntime().availableProcessors();
    }

    /**
     * Reads CPU hardware name from {@code /proc/cpuinfo}.
     *
     * @return the "Hardware" field value, or {@code "unknown"}
     */
    @NonNull
    public static String getCpuHardware() {
        try (BufferedReader r = new BufferedReader(new FileReader("/proc/cpuinfo"))) {
            String line;
            while ((line = r.readLine()) != null) {
                if (line.startsWith("Hardware")) {
                    int colon = line.indexOf(':');
                    if (colon >= 0) return line.substring(colon + 1).trim();
                }
            }
        } catch (IOException e) {
            Logger.w(TAG, "Could not read /proc/cpuinfo: " + e.getMessage());
        }
        return "unknown";
    }

    // -------------------------------------------------------------------------
    // Android info
    // -------------------------------------------------------------------------

    /**
     * Returns a summary string of key device properties for diagnostic logging.
     *
     * @return multi-line device information string
     */
    @NonNull
    public static String getDeviceInfo() {
        return "Model: " + Build.MODEL + "\n"
                + "Manufacturer: " + Build.MANUFACTURER + "\n"
                + "Android SDK: " + Build.VERSION.SDK_INT + "\n"
                + "Release: " + Build.VERSION.RELEASE + "\n"
                + "ABI: " + getPrimaryAbi() + "\n"
                + "Kernel: " + getKernelVersion() + "\n"
                + "SELinux: " + getSELinuxStatus() + "\n"
                + "CPU cores: " + getCpuCoreCount();
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static long parseProcMemLine(@NonNull String line) {
        // Format: "MemTotal:    8192000 kB"
        String[] parts = line.split("\\s+");
        if (parts.length >= 2) {
            try {
                return Long.parseLong(parts[1]);
            } catch (NumberFormatException e) {
                return -1;
            }
        }
        return -1;
    }
}
