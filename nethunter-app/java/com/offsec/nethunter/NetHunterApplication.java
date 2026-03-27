package com.offsec.nethunter;

import android.app.Application;
import android.content.Context;
import android.os.StrictMode;
import android.util.Log;

import androidx.annotation.NonNull;

import com.offsec.nethunter.utils.Logger;
import com.offsec.nethunter.utils.NetHunterPaths;
import com.offsec.nethunter.utils.SystemUtils;

import java.io.File;
import java.lang.Thread.UncaughtExceptionHandler;

/**
 * NetHunter Application class.
 *
 * <p>Serves as the entry point for the application process. Initialises global state including
 * the logger, path resolver, root-availability check, and an uncaught-exception handler that
 * captures crash reports to disk before delegating to the default system handler.
 */
public class NetHunterApplication extends Application {

    private static final String TAG = "NetHunterApplication";

    /** Singleton instance, set once in {@link #onCreate()}. */
    private static NetHunterApplication sInstance;

    /** Whether root access was confirmed at startup. */
    private boolean mRootAvailable;

    // -------------------------------------------------------------------------
    // Singleton
    // -------------------------------------------------------------------------

    /**
     * Returns the singleton {@link NetHunterApplication} instance.
     *
     * @return the application singleton
     * @throws IllegalStateException if called before {@link #onCreate()} has run
     */
    @NonNull
    public static NetHunterApplication getInstance() {
        if (sInstance == null) {
            throw new IllegalStateException("Application not yet initialised");
        }
        return sInstance;
    }

    // -------------------------------------------------------------------------
    // Lifecycle
    // -------------------------------------------------------------------------

    @Override
    public void onCreate() {
        super.onCreate();
        sInstance = this;

        initLogger();
        initPaths();
        checkRoot();
        installUncaughtExceptionHandler();

        Logger.i(TAG, "NetHunter application started (root=" + mRootAvailable + ")");
    }

    // -------------------------------------------------------------------------
    // Initialisation helpers
    // -------------------------------------------------------------------------

    /** Initialises the file-based logger as early as possible. */
    private void initLogger() {
        Logger.init(this);
        Logger.i(TAG, "Logger initialised");
    }

    /**
     * Ensures all required application directories exist on the file system.
     * Non-fatal: logs a warning if creation fails rather than crashing.
     */
    private void initPaths() {
        try {
            NetHunterPaths.ensureDirectoriesExist(this);
            Logger.i(TAG, "Path initialisation complete");
        } catch (Exception e) {
            Logger.w(TAG, "Path initialisation encountered an error: " + e.getMessage());
        }
    }

    /** Performs a quick, non-blocking root availability check. */
    private void checkRoot() {
        mRootAvailable = SystemUtils.isRootAvailable();
        if (!mRootAvailable) {
            Logger.w(TAG, "Root access is NOT available – some features will be disabled");
        }
    }

    /**
     * Installs a global {@link UncaughtExceptionHandler} that writes crash details to the log
     * file before handing off to the system's default handler.
     */
    private void installUncaughtExceptionHandler() {
        final UncaughtExceptionHandler defaultHandler =
                Thread.getDefaultUncaughtExceptionHandler();

        Thread.setDefaultUncaughtExceptionHandler((thread, throwable) -> {
            try {
                Logger.e(TAG, "UNCAUGHT EXCEPTION on thread [" + thread.getName() + "]", throwable);
                Logger.flush();
            } catch (Exception ignored) {
                // Must not throw inside the crash handler.
            }
            if (defaultHandler != null) {
                defaultHandler.uncaughtException(thread, throwable);
            }
        });
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /**
     * Returns whether root access is available on this device.
     *
     * @return {@code true} if a root binary was located and responded successfully
     */
    public boolean isRootAvailable() {
        return mRootAvailable;
    }

    /**
     * Re-evaluates root availability and updates the cached result.
     *
     * @return the refreshed root-availability status
     */
    public boolean refreshRootStatus() {
        mRootAvailable = SystemUtils.isRootAvailable();
        Logger.i(TAG, "Root status refreshed: " + mRootAvailable);
        return mRootAvailable;
    }

    /** Returns the application {@link Context} (equivalent to {@code getApplicationContext()}). */
    @NonNull
    public Context getAppContext() {
        return getApplicationContext();
    }
}
