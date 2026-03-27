package com.offsec.nethunter.utils;

import android.util.Log;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * Utility class for executing shell commands, managing NetHunter paths,
 * and reading system variables.
 */
public class SystemUtils {

    private static final String TAG = "SystemUtils";

    // --- NetHunter Path Constants ---
    public static final String NH_BASE_PATH        = "/data/local/nhsystem";
    public static final String NH_KALI_PATH        = NH_BASE_PATH + "/kali-arm64";
    public static final String NH_SCRIPTS_PATH     = NH_KALI_PATH + "/scripts";
    public static final String NH_BOOTKALI_SCRIPT  = "/system/bin/bootkali";
    public static final String NH_SDCARD_PATH      = "/sdcard/nethunter";
    public static final String NH_FIRMWARE_PATH    = NH_SDCARD_PATH + "/firmware";
    public static final String NH_LOGS_PATH        = NH_SDCARD_PATH + "/logs";
    public static final String NH_MODULES_PATH     = NH_SDCARD_PATH + "/modules";
    public static final String FLIPPER_UART_DEV    = "/dev/ttyACM0";
    public static final String FLIPPER_UART_DEV_ALT = "/dev/ttyUSB0";

    // --- Shell Command Execution ---

    /**
     * Execute a shell command as root (su) and return the output.
     */
    public static CommandResult runAsRoot(String command) {
        return runCommand(new String[]{"su", "-c", command});
    }

    /**
     * Execute a shell command as root (su) with a timeout.
     */
    public static CommandResult runAsRoot(String command, long timeoutSeconds) {
        return runCommand(new String[]{"su", "-c", command}, timeoutSeconds);
    }

    /**
     * Execute a shell command and return the combined stdout/stderr output.
     */
    public static CommandResult runCommand(String[] args) {
        return runCommand(args, 30L);
    }

    /**
     * Execute a shell command with a timeout and return the result.
     */
    public static CommandResult runCommand(String[] args, long timeoutSeconds) {
        StringBuilder stdout = new StringBuilder();
        StringBuilder stderr = new StringBuilder();
        int exitCode = -1;

        try {
            Process process = new ProcessBuilder(args)
                .redirectErrorStream(false)
                .start();

            // Read stdout in background
            Thread stdoutThread = new Thread(() -> {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(process.getInputStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        stdout.append(line).append("\n");
                    }
                } catch (IOException e) {
                    Log.w(TAG, "Error reading stdout", e);
                }
            });

            // Read stderr in background
            Thread stderrThread = new Thread(() -> {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(process.getErrorStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        stderr.append(line).append("\n");
                    }
                } catch (IOException e) {
                    Log.w(TAG, "Error reading stderr", e);
                }
            });

            stdoutThread.start();
            stderrThread.start();

            boolean finished = process.waitFor(timeoutSeconds, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                Log.w(TAG, "Command timed out: " + Arrays.toString(args));
                return new CommandResult(-1, stdout.toString(), "Command timed out");
            }

            stdoutThread.join(1000);
            stderrThread.join(1000);
            exitCode = process.exitValue();

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            Log.e(TAG, "Command interrupted", e);
        } catch (IOException e) {
            Log.e(TAG, "Command execution error: " + Arrays.toString(args), e);
            return new CommandResult(-1, "", e.getMessage());
        }

        return new CommandResult(exitCode, stdout.toString().trim(), stderr.toString().trim());
    }

    /**
     * Check if root (su) is available.
     */
    public static boolean isRootAvailable() {
        CommandResult result = runCommand(new String[]{"su", "-c", "id"}, 5);
        return result.exitCode == 0 && result.stdout.contains("uid=0");
    }

    /**
     * Check if the Kali chroot is installed.
     */
    public static boolean isChrootInstalled() {
        return new File(NH_KALI_PATH).isDirectory();
    }

    /**
     * Check if a serial device exists.
     */
    public static boolean deviceExists(String devicePath) {
        return new File(devicePath).exists();
    }

    /**
     * Get the Flipper UART device path (tries primary, then fallback).
     */
    public static String getFlipperUartDevice() {
        if (deviceExists(FLIPPER_UART_DEV)) return FLIPPER_UART_DEV;
        if (deviceExists(FLIPPER_UART_DEV_ALT)) return FLIPPER_UART_DEV_ALT;
        return null;
    }

    /**
     * Read a system property using getprop.
     */
    public static String getSystemProperty(String property) {
        CommandResult result = runCommand(new String[]{"getprop", property}, 5);
        if (result.exitCode == 0) {
            return result.stdout.trim();
        }
        return "";
    }

    /**
     * Get Android build fingerprint.
     */
    public static String getBuildFingerprint() {
        return getSystemProperty("ro.build.fingerprint");
    }

    /**
     * Get kernel version string.
     */
    public static String getKernelVersion() {
        CommandResult result = runCommand(new String[]{"uname", "-r"}, 5);
        return result.exitCode == 0 ? result.stdout.trim() : "unknown";
    }

    /**
     * Check available disk space in bytes at the given path.
     */
    public static long getAvailableDiskSpace(String path) {
        File f = new File(path);
        if (f.exists()) {
            return f.getUsableSpace();
        }
        return -1L;
    }

    /**
     * List USB devices connected to the device.
     */
    public static List<String> listUsbDevices() {
        List<String> devices = new ArrayList<>();
        CommandResult result = runAsRoot("ls /dev/bus/usb/ 2>/dev/null");
        if (result.exitCode == 0 && !result.stdout.isEmpty()) {
            for (String line : result.stdout.split("\n")) {
                String trimmed = line.trim();
                if (!trimmed.isEmpty()) {
                    devices.add("/dev/bus/usb/" + trimmed);
                }
            }
        }
        return devices;
    }

    /**
     * Set file permissions using chmod.
     */
    public static boolean setFilePermissions(String path, String permissions) {
        CommandResult result = runAsRoot("chmod " + permissions + " " + path);
        return result.exitCode == 0;
    }

    /**
     * Create directory with parents.
     */
    public static boolean mkdirs(String path) {
        File dir = new File(path);
        if (dir.exists()) return true;
        return dir.mkdirs();
    }

    // --- Result class ---

    public static class CommandResult {
        public final int exitCode;
        public final String stdout;
        public final String stderr;

        public CommandResult(int exitCode, String stdout, String stderr) {
            this.exitCode = exitCode;
            this.stdout   = stdout != null ? stdout : "";
            this.stderr   = stderr != null ? stderr : "";
        }

        public boolean isSuccess() {
            return exitCode == 0;
        }

        @Override
        public String toString() {
            return "CommandResult{exitCode=" + exitCode +
                ", stdout='" + stdout + "', stderr='" + stderr + "'}";
        }
    }
}
