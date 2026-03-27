package com.offsec.nethunter.utils;

import android.util.Log;

import java.io.BufferedReader;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;

/**
 * RootUtils - Utility class for executing shell commands with root privileges.
 *
 * <p>All methods in this class are static and work by opening a {@code su} shell
 * subprocess and piping commands to it. Commands are executed synchronously;
 * use a background thread or {@link android.os.AsyncTask} equivalent to avoid
 * blocking the main thread.</p>
 *
 * <p><strong>Security note:</strong> Never pass untrusted user input directly to
 * {@link #executeCommand(String)} without sanitising it first.</p>
 */
public final class RootUtils {

    private static final String TAG = "RootUtils";

    /** Prevent instantiation of this utility class. */
    private RootUtils() {}

    /**
     * Checks whether root access (su binary) is available on this device.
     *
     * <p>The check is performed by running {@code id} via {@code su} and verifying
     * that the output contains {@code "uid=0"} (root UID).</p>
     *
     * @return {@code true} if root access is available, {@code false} otherwise
     */
    public static boolean isRootAvailable() {
        Process process = null;
        try {
            process = Runtime.getRuntime().exec(new String[]{"su", "-c", "id"});
            BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream()));
            String line = reader.readLine();
            process.waitFor();
            return line != null && line.contains("uid=0");
        } catch (IOException | InterruptedException e) {
            Log.d(TAG, "Root check failed: " + e.getMessage());
            return false;
        } finally {
            if (process != null) process.destroy();
        }
    }

    /**
     * Executes a single shell command as root using {@code su}.
     *
     * <p>The command is written to the {@code su} process stdin and terminated
     * with {@code exit}. Both stdout and stderr are logged at VERBOSE / WARN level
     * respectively.</p>
     *
     * @param command the shell command to execute (must not be {@code null})
     * @return the combined stdout output of the command, or an empty string on failure
     * @throws IllegalArgumentException if {@code command} is null or empty
     */
    public static String executeCommand(String command) {
        if (command == null || command.trim().isEmpty()) {
            throw new IllegalArgumentException("command must not be null or empty");
        }

        StringBuilder output = new StringBuilder();
        Process process = null;

        try {
            process = Runtime.getRuntime().exec("su");
            DataOutputStream stdin = new DataOutputStream(process.getOutputStream());
            BufferedReader stdout = new BufferedReader(
                new InputStreamReader(process.getInputStream()));
            BufferedReader stderr = new BufferedReader(
                new InputStreamReader(process.getErrorStream()));

            stdin.writeBytes(command + "\n");
            stdin.writeBytes("exit\n");
            stdin.flush();

            String line;
            while ((line = stdout.readLine()) != null) {
                output.append(line).append("\n");
                Log.v(TAG, "stdout: " + line);
            }
            while ((line = stderr.readLine()) != null) {
                Log.w(TAG, "stderr: " + line);
            }

            int exitCode = process.waitFor();
            Log.d(TAG, "Command '" + command + "' exited with code " + exitCode);

        } catch (IOException | InterruptedException e) {
            Log.e(TAG, "Failed to execute command: " + command, e);
        } finally {
            if (process != null) process.destroy();
        }

        return output.toString().trim();
    }

    /**
     * Executes a shell command as root and returns whether it exited successfully
     * (exit code 0).
     *
     * @param command the shell command to test
     * @return {@code true} if the command exits with code 0
     */
    public static boolean executeCommandSuccess(String command) {
        if (command == null || command.trim().isEmpty()) {
            throw new IllegalArgumentException("command must not be null or empty");
        }

        Process process = null;
        try {
            process = Runtime.getRuntime().exec("su");
            DataOutputStream stdin = new DataOutputStream(process.getOutputStream());
            stdin.writeBytes(command + "\n");
            stdin.writeBytes("exit\n");
            stdin.flush();
            return process.waitFor() == 0;
        } catch (IOException | InterruptedException e) {
            Log.e(TAG, "Failed to execute command: " + command, e);
            return false;
        } finally {
            if (process != null) process.destroy();
        }
    }
}
