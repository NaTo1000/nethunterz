package com.offsec.nethunter.utils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Executes shell commands with optional root elevation.
 *
 * <p>Supports three execution modes:
 * <ul>
 *   <li><strong>Synchronous</strong> – {@link #executeSync(String)} blocks the
 *       calling thread and returns the exit code.</li>
 *   <li><strong>Asynchronous</strong> – {@link #executeAsync(String, Callback)}
 *       runs on a pool thread and delivers output/completion via {@link Callback}.</li>
 *   <li><strong>Persistent root shell</strong> – {@link #openRootShell()} /
 *       {@link #writeToShell(String)} reuse a single long-lived {@code su} process,
 *       avoiding repeated shell-spawn overhead.</li>
 * </ul>
 *
 * <p>Thread-safe. The persistent root shell is opened lazily on first use.
 */
public class ShellExecutor {

    private static final String TAG = "ShellExecutor";

    private static final int    SYNC_TIMEOUT_SEC = 60;
    private static final String SU_BINARY        = "su";
    private static final String SH_BINARY        = "sh";

    // -------------------------------------------------------------------------
    // Callback interface
    // -------------------------------------------------------------------------

    /** Receives output lines and lifecycle events from an async execution. */
    public interface Callback {
        /**
         * Called for each line of standard output/error produced by the command.
         *
         * @param line the output line, without a trailing newline
         */
        void onOutput(@NonNull String line);

        /**
         * Called once when the command process exits.
         *
         * @param exitCode the process exit code (0 = success)
         */
        void onComplete(int exitCode);

        /**
         * Called when a non-recoverable error prevents execution.
         *
         * @param error a human-readable description of the error
         */
        void onError(@NonNull String error);
    }

    // -------------------------------------------------------------------------
    // Singleton
    // -------------------------------------------------------------------------

    private static volatile ShellExecutor sInstance;

    @NonNull
    public static ShellExecutor getInstance() {
        if (sInstance == null) {
            synchronized (ShellExecutor.class) {
                if (sInstance == null) {
                    sInstance = new ShellExecutor();
                }
            }
        }
        return sInstance;
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private final ExecutorService mPool = Executors.newCachedThreadPool();

    // Persistent root shell state
    private final Object       mShellLock  = new Object();
    private Process            mRootShell;
    private PrintWriter        mShellInput;
    private final AtomicBoolean mShellOpen = new AtomicBoolean(false);

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    private ShellExecutor() {}

    // -------------------------------------------------------------------------
    // Synchronous execution
    // -------------------------------------------------------------------------

    /**
     * Executes a root shell command synchronously, blocking the calling thread
     * until the command exits or a {@value #SYNC_TIMEOUT_SEC}-second timeout
     * elapses.
     *
     * @param command the shell command to run as root
     * @return the exit code of the command process, or {@code -1} on error/timeout
     */
    public int executeSync(@NonNull String command) {
        return executeSyncInternal(command, true, SYNC_TIMEOUT_SEC);
    }

    /**
     * Executes a non-root shell command synchronously.
     *
     * @param command the shell command to run
     * @return the exit code, or {@code -1} on error/timeout
     */
    public int executeSyncNoRoot(@NonNull String command) {
        return executeSyncInternal(command, false, SYNC_TIMEOUT_SEC);
    }

    private int executeSyncInternal(@NonNull String command, boolean asRoot, int timeoutSec) {
        String[] args = asRoot
                ? new String[]{SU_BINARY, "-c", command}
                : new String[]{SH_BINARY, "-c", command};
        try {
            Process proc = Runtime.getRuntime().exec(args);
            // Drain stdout/stderr to prevent the pipe buffer from filling and blocking
            drainStream(proc);
            boolean finished = proc.waitFor(timeoutSec, TimeUnit.SECONDS);
            if (!finished) {
                proc.destroyForcibly();
                Logger.w(TAG, "Command timed out after " + timeoutSec + "s: " + command);
                return -1;
            }
            return proc.exitValue();
        } catch (IOException | InterruptedException e) {
            Logger.e(TAG, "Sync execution error: " + e.getMessage(), e);
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            return -1;
        }
    }

    // -------------------------------------------------------------------------
    // Asynchronous execution
    // -------------------------------------------------------------------------

    /**
     * Executes a root shell command asynchronously.
     *
     * @param command  the shell command to run as root
     * @param callback receives output/completion events on the pool thread
     * @return a {@link Future} that can be used to cancel the execution
     */
    @NonNull
    public Future<?> executeAsync(@NonNull String command, @Nullable Callback callback) {
        return mPool.submit(() -> runAsync(command, true, callback));
    }

    /**
     * Executes a non-root shell command asynchronously.
     *
     * @param command  the shell command to run
     * @param callback receives output/completion events on the pool thread
     * @return a {@link Future} that can be used to cancel the execution
     */
    @NonNull
    public Future<?> executeAsyncNoRoot(@NonNull String command, @Nullable Callback callback) {
        return mPool.submit(() -> runAsync(command, false, callback));
    }

    private void runAsync(@NonNull String command, boolean asRoot,
            @Nullable Callback callback) {
        String[] args = asRoot
                ? new String[]{SU_BINARY, "-c", command}
                : new String[]{SH_BINARY, "-c", command};
        try {
            Process proc = Runtime.getRuntime().exec(args);
            try (BufferedReader out = new BufferedReader(
                         new InputStreamReader(proc.getInputStream()));
                 BufferedReader err = new BufferedReader(
                         new InputStreamReader(proc.getErrorStream()))) {

                // Merge stdout + stderr by reading them in alternation
                String line;
                while ((line = out.readLine()) != null) {
                    if (callback != null) callback.onOutput(line);
                }
                while ((line = err.readLine()) != null) {
                    if (callback != null) callback.onOutput(line);
                }
            }
            int exitCode = proc.waitFor();
            if (callback != null) callback.onComplete(exitCode);
        } catch (IOException | InterruptedException e) {
            Logger.e(TAG, "Async execution error for [" + command + "]: " + e.getMessage(), e);
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            if (callback != null) callback.onError(e.getMessage());
        }
    }

    // -------------------------------------------------------------------------
    // Persistent root shell
    // -------------------------------------------------------------------------

    /**
     * Opens a persistent {@code su} shell session. Subsequent calls to
     * {@link #writeToShell(String)} send commands to this shell without the
     * overhead of spawning a new process each time.
     *
     * @return {@code true} if the shell was opened (or was already open)
     */
    public boolean openRootShell() {
        synchronized (mShellLock) {
            if (mShellOpen.get()) return true;
            try {
                mRootShell = Runtime.getRuntime().exec(new String[]{SU_BINARY});
                mShellInput = new PrintWriter(
                        new OutputStreamWriter(mRootShell.getOutputStream()), true);
                mShellOpen.set(true);
                Logger.i(TAG, "Persistent root shell opened");
                return true;
            } catch (IOException e) {
                Logger.e(TAG, "Failed to open root shell: " + e.getMessage(), e);
                return false;
            }
        }
    }

    /**
     * Writes a command to the persistent root shell.
     *
     * @param command the command to execute; a newline is appended automatically
     * @return {@code true} if the command was written successfully
     */
    public boolean writeToShell(@NonNull String command) {
        synchronized (mShellLock) {
            if (!mShellOpen.get() || mShellInput == null) {
                Logger.w(TAG, "Root shell not open; call openRootShell() first");
                return false;
            }
            mShellInput.println(command);
            return !mShellInput.checkError();
        }
    }

    /**
     * Closes the persistent root shell and releases resources.
     */
    public void closeRootShell() {
        synchronized (mShellLock) {
            if (!mShellOpen.get()) return;
            writeToShell("exit");
            if (mShellInput != null) mShellInput.close();
            if (mRootShell  != null) mRootShell.destroyForcibly();
            mShellOpen.set(false);
            Logger.i(TAG, "Persistent root shell closed");
        }
    }

    // -------------------------------------------------------------------------
    // Convenience: execute a list of commands
    // -------------------------------------------------------------------------

    /**
     * Executes a list of root commands sequentially, stopping if any command
     * returns a non-zero exit code.
     *
     * @param commands the list of commands to execute
     * @return the exit code of the first failed command, or {@code 0} if all
     *         commands succeeded
     */
    public int executeBatch(@NonNull List<String> commands) {
        for (String cmd : commands) {
            int code = executeSync(cmd);
            if (code != 0) {
                Logger.w(TAG, "Batch command failed (exit " + code + "): " + cmd);
                return code;
            }
        }
        return 0;
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /** Drains stdout and stderr of a process on background threads. */
    private void drainStream(@NonNull Process proc) {
        mPool.submit(() -> {
            try (BufferedReader r = new BufferedReader(
                    new InputStreamReader(proc.getInputStream()))) {
                while (r.readLine() != null) { /* discard */ }
            } catch (IOException ignored) {}
        });
        mPool.submit(() -> {
            try (BufferedReader r = new BufferedReader(
                    new InputStreamReader(proc.getErrorStream()))) {
                while (r.readLine() != null) { /* discard */ }
            } catch (IOException ignored) {}
        });
    }
}
