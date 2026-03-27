package com.offsec.nethunter.utils;

import android.content.Context;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Application-wide logger that writes to both Android Logcat and a rotating
 * set of on-disk log files.
 *
 * <p>Log files are stored in {@link NetHunterPaths#LOGS_DIR} and are rotated
 * when the current file exceeds {@value #MAX_FILE_SIZE_BYTES} bytes. Up to
 * {@value #MAX_ROTATED_FILES} old files are retained.
 *
 * <p>All disk writes are performed on a single-threaded background
 * {@link ExecutorService} to avoid blocking the calling thread.
 *
 * <p>Usage:
 * <pre>{@code
 *   // Initialise once in Application.onCreate():
 *   Logger.init(context);
 *
 *   // Log at any level from anywhere:
 *   Logger.i(TAG, "Service started");
 *   Logger.e(TAG, "Unexpected error", exception);
 * }</pre>
 */
public final class Logger {

    // -------------------------------------------------------------------------
    // Constants
    // -------------------------------------------------------------------------

    private static final long MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
    private static final int  MAX_ROTATED_FILES   = 3;
    private static final String LOG_FILE_NAME     = "nethunter.log";
    private static final SimpleDateFormat DATE_FMT =
            new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US);

    // -------------------------------------------------------------------------
    // Log levels
    // -------------------------------------------------------------------------

    public enum Level {
        VERBOSE, DEBUG, INFO, WARN, ERROR
    }

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    private static volatile File              sLogFile;
    private static volatile Level             sMinLevel = Level.VERBOSE;
    private static final ExecutorService      sWriter   =
            Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "Logger-writer");
                t.setDaemon(true);
                return t;
            });

    private Logger() {}

    // -------------------------------------------------------------------------
    // Initialisation
    // -------------------------------------------------------------------------

    /**
     * Initialises the file logger. Must be called once from
     * {@link android.app.Application#onCreate()} before any log calls.
     *
     * @param context the application context used to resolve the log directory
     */
    public static void init(@NonNull Context context) {
        File logsDir = new File(NetHunterPaths.LOGS_DIR);
        if (!logsDir.exists()) logsDir.mkdirs();
        sLogFile = new File(logsDir, LOG_FILE_NAME);
        i("Logger", "File logger initialised at " + sLogFile.getAbsolutePath());
    }

    /**
     * Sets the minimum log level. Messages below this level are silently
     * discarded.
     *
     * @param level the minimum level to record
     */
    public static void setMinLevel(@NonNull Level level) {
        sMinLevel = level;
    }

    // -------------------------------------------------------------------------
    // Logging API
    // -------------------------------------------------------------------------

    /** Logs at {@link Level#VERBOSE}. */
    public static void v(@NonNull String tag, @NonNull String msg) {
        log(Level.VERBOSE, tag, msg, null);
    }

    /** Logs at {@link Level#DEBUG}. */
    public static void d(@NonNull String tag, @NonNull String msg) {
        log(Level.DEBUG, tag, msg, null);
    }

    /** Logs at {@link Level#INFO}. */
    public static void i(@NonNull String tag, @NonNull String msg) {
        log(Level.INFO, tag, msg, null);
    }

    /** Logs at {@link Level#WARN}. */
    public static void w(@NonNull String tag, @NonNull String msg) {
        log(Level.WARN, tag, msg, null);
    }

    /** Logs at {@link Level#ERROR} without a throwable. */
    public static void e(@NonNull String tag, @NonNull String msg) {
        log(Level.ERROR, tag, msg, null);
    }

    /**
     * Logs at {@link Level#ERROR} with a {@link Throwable}.
     *
     * @param tag       the log tag
     * @param msg       the message
     * @param throwable the exception to log (stack trace is appended)
     */
    public static void e(@NonNull String tag, @NonNull String msg,
            @Nullable Throwable throwable) {
        log(Level.ERROR, tag, msg, throwable);
    }

    // -------------------------------------------------------------------------
    // Core
    // -------------------------------------------------------------------------

    private static void log(@NonNull Level level, @NonNull String tag,
            @NonNull String msg, @Nullable Throwable throwable) {
        if (level.ordinal() < sMinLevel.ordinal()) return;

        // Write to Logcat synchronously (cheap)
        logToLogcat(level, tag, msg, throwable);

        // Write to file asynchronously
        if (sLogFile != null) {
            final String line = formatLine(level, tag, msg, throwable);
            sWriter.execute(() -> writeToFile(line));
        }
    }

    private static void logToLogcat(@NonNull Level level, @NonNull String tag,
            @NonNull String msg, @Nullable Throwable t) {
        switch (level) {
            case VERBOSE: Log.v(tag, msg, t); break;
            case DEBUG:   Log.d(tag, msg, t); break;
            case INFO:    Log.i(tag, msg, t); break;
            case WARN:    Log.w(tag, msg, t); break;
            case ERROR:   Log.e(tag, msg, t); break;
        }
    }

    @NonNull
    private static String formatLine(@NonNull Level level, @NonNull String tag,
            @NonNull String msg, @Nullable Throwable t) {
        StringBuilder sb = new StringBuilder();
        sb.append(DATE_FMT.format(new Date()))
          .append(' ')
          .append(level.name().charAt(0))
          .append('/')
          .append(tag)
          .append(": ")
          .append(msg);
        if (t != null) {
            sb.append('\n');
            StringWriter sw = new StringWriter();
            t.printStackTrace(new PrintWriter(sw));
            sb.append(sw.toString());
        }
        return sb.toString();
    }

    // -------------------------------------------------------------------------
    // File writing with rotation
    // -------------------------------------------------------------------------

    private static void writeToFile(@NonNull String line) {
        if (sLogFile == null) return;
        try {
            rotateIfNeeded();
            try (FileOutputStream fos = new FileOutputStream(sLogFile, true);
                 OutputStreamWriter writer = new OutputStreamWriter(fos, "UTF-8")) {
                writer.write(line);
                writer.write('\n');
            }
        } catch (IOException e) {
            Log.e("Logger", "Failed to write log: " + e.getMessage());
        }
    }

    private static void rotateIfNeeded() {
        if (sLogFile == null || !sLogFile.exists()) return;
        if (sLogFile.length() < MAX_FILE_SIZE_BYTES) return;

        // Shift older backups: .2 → .3, .1 → .2
        for (int i = MAX_ROTATED_FILES - 1; i >= 1; i--) {
            File older = new File(sLogFile.getPath() + "." + i);
            File newer = new File(sLogFile.getPath() + "." + (i + 1));
            if (older.exists()) older.renameTo(newer);
        }
        sLogFile.renameTo(new File(sLogFile.getPath() + ".1"));
    }

    // -------------------------------------------------------------------------
    // Flush
    // -------------------------------------------------------------------------

    /**
     * Blocks until all pending log writes have been flushed to disk.
     * Useful before crash reporting or process exit.
     */
    public static void flush() {
        try {
            sWriter.submit(() -> {}).get(5, java.util.concurrent.TimeUnit.SECONDS);
        } catch (Exception ignored) {}
    }
}
