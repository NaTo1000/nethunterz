package com.offsec.nethunter.GPS;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.offsec.nethunter.utils.Logger;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Streams raw NMEA sentences from either a file or a TCP socket to a registered
 * {@link StreamCallback}.
 *
 * <p>Supports two modes:
 * <ul>
 *   <li><strong>File mode</strong> – replays sentences from a static NMEA log file,
 *       optionally looping.</li>
 *   <li><strong>Socket mode</strong> – connects to a TCP host/port (e.g. gpsd) and
 *       reads lines as they arrive, with automatic reconnection.</li>
 * </ul>
 *
 * <p>All I/O is performed on a dedicated background thread; the caller is not
 * blocked. Thread safety is achieved through volatile state flags and the
 * {@link ExecutorService}.
 */
public class NMEADataStreamer {

    private static final String TAG = "NMEADataStreamer";

    private static final int SOCKET_TIMEOUT_MS  = 5_000;
    private static final int RECONNECT_DELAY_MS = 3_000;
    private static final int MAX_RETRIES        = 10;

    // -------------------------------------------------------------------------
    // Connection state enum
    // -------------------------------------------------------------------------

    /** Observable connection lifecycle states. */
    public enum State {
        IDLE,
        CONNECTING,
        CONNECTED,
        RECONNECTING,
        STOPPED
    }

    // -------------------------------------------------------------------------
    // Callback interface
    // -------------------------------------------------------------------------

    /** Receives NMEA lines and state-change events from the streamer. */
    public interface StreamCallback {
        /**
         * Called for each raw NMEA sentence received from the source.
         *
         * @param sentence a single NMEA line, without a trailing newline
         */
        void onSentence(@NonNull String sentence);

        /**
         * Called whenever the streamer's connection state changes.
         *
         * @param state the new state
         */
        void onStateChanged(@NonNull State state);

        /**
         * Called when a non-recoverable error occurs.
         *
         * @param message a human-readable description of the error
         */
        void onError(@NonNull String message);
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private final ExecutorService mExecutor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean   mActive   = new AtomicBoolean(false);

    private StreamCallback mCallback;
    private Future<?>      mStreamFuture;
    private volatile State mState = State.IDLE;

    // Socket-mode parameters
    private String  mHost;
    private int     mPort;

    // File-mode parameters
    private File    mNmeaFile;
    private boolean mLoop;

    // -------------------------------------------------------------------------
    // Configuration
    // -------------------------------------------------------------------------

    /**
     * Configures the streamer for TCP socket mode.
     *
     * @param host     the TCP host (e.g. "127.0.0.1")
     * @param port     the TCP port (e.g. 2947)
     * @param callback event callback; must not be {@code null}
     */
    public void configureSocket(@NonNull String host, int port, @NonNull StreamCallback callback) {
        mHost     = host;
        mPort     = port;
        mCallback = callback;
        mNmeaFile = null;
        Logger.d(TAG, "Configured for socket: " + host + ":" + port);
    }

    /**
     * Configures the streamer for file-replay mode.
     *
     * @param file     the NMEA log file to read; must exist and be readable
     * @param loop     if {@code true} the file is replayed indefinitely
     * @param callback event callback; must not be {@code null}
     */
    public void configureFile(@NonNull File file, boolean loop, @NonNull StreamCallback callback) {
        mNmeaFile = file;
        mLoop     = loop;
        mCallback = callback;
        mHost     = null;
        Logger.d(TAG, "Configured for file: " + file.getAbsolutePath() + " loop=" + loop);
    }

    // -------------------------------------------------------------------------
    // Start / Stop
    // -------------------------------------------------------------------------

    /**
     * Starts streaming in the background. A no-op if already active.
     *
     * @throws IllegalStateException if neither socket nor file mode has been configured
     */
    public synchronized void start() {
        if (mActive.get()) {
            Logger.w(TAG, "Streamer already running");
            return;
        }
        if (mCallback == null) {
            throw new IllegalStateException("Streamer not configured – call configureSocket() or configureFile() first");
        }
        mActive.set(true);
        transitionTo(State.CONNECTING);

        if (mNmeaFile != null) {
            mStreamFuture = mExecutor.submit(this::runFileStream);
        } else if (mHost != null) {
            mStreamFuture = mExecutor.submit(this::runSocketStream);
        } else {
            throw new IllegalStateException("No source configured");
        }
        Logger.i(TAG, "Streamer started");
    }

    /**
     * Stops the active stream. Blocks briefly until the background task
     * acknowledges the stop request, then returns.
     */
    public synchronized void stop() {
        if (!mActive.get()) return;
        mActive.set(false);
        if (mStreamFuture != null) {
            mStreamFuture.cancel(true);
        }
        transitionTo(State.STOPPED);
        Logger.i(TAG, "Streamer stopped");
    }

    /** Returns the current connection state. */
    @NonNull
    public State getState() {
        return mState;
    }

    /** Returns {@code true} if the stream is currently active. */
    public boolean isActive() {
        return mActive.get();
    }

    // -------------------------------------------------------------------------
    // Socket stream
    // -------------------------------------------------------------------------

    private void runSocketStream() {
        int retries = 0;
        while (mActive.get() && retries < MAX_RETRIES) {
            transitionTo(retries == 0 ? State.CONNECTING : State.RECONNECTING);
            try (Socket socket = new Socket()) {
                socket.connect(new InetSocketAddress(mHost, mPort), SOCKET_TIMEOUT_MS);
                socket.setSoTimeout(SOCKET_TIMEOUT_MS);
                transitionTo(State.CONNECTED);
                retries = 0;
                Logger.i(TAG, "Socket connected to " + mHost + ":" + mPort);

                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(socket.getInputStream()))) {
                    String line;
                    while (mActive.get() && (line = reader.readLine()) != null) {
                        String trimmed = line.trim();
                        if (!trimmed.isEmpty() && mCallback != null) {
                            mCallback.onSentence(trimmed);
                        }
                    }
                }
            } catch (IOException e) {
                if (mActive.get()) {
                    retries++;
                    Logger.w(TAG, "Socket error (attempt " + retries + "): " + e.getMessage());
                    sleep(RECONNECT_DELAY_MS);
                }
            }
        }
        if (mActive.get() && retries >= MAX_RETRIES && mCallback != null) {
            mCallback.onError("Max reconnection attempts reached (" + MAX_RETRIES + ")");
        }
        transitionTo(State.STOPPED);
        mActive.set(false);
    }

    // -------------------------------------------------------------------------
    // File stream
    // -------------------------------------------------------------------------

    private void runFileStream() {
        transitionTo(State.CONNECTING);
        if (!mNmeaFile.exists() || !mNmeaFile.canRead()) {
            Logger.e(TAG, "NMEA file not readable: " + mNmeaFile.getAbsolutePath());
            if (mCallback != null) {
                mCallback.onError("Cannot read NMEA file: " + mNmeaFile.getAbsolutePath());
            }
            transitionTo(State.STOPPED);
            mActive.set(false);
            return;
        }

        transitionTo(State.CONNECTED);
        do {
            try (BufferedReader reader = new BufferedReader(new FileReader(mNmeaFile))) {
                String line;
                while (mActive.get() && (line = reader.readLine()) != null) {
                    String trimmed = line.trim();
                    if (!trimmed.isEmpty() && mCallback != null) {
                        mCallback.onSentence(trimmed);
                    }
                    // Throttle file replay to ~10 Hz so it approximates real GPS rate
                    sleep(100);
                }
            } catch (IOException e) {
                Logger.e(TAG, "File read error: " + e.getMessage());
                if (mCallback != null) {
                    mCallback.onError("File read error: " + e.getMessage());
                }
                mActive.set(false);
            }
        } while (mActive.get() && mLoop);

        transitionTo(State.STOPPED);
        mActive.set(false);
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private void transitionTo(@NonNull State newState) {
        if (mState == newState) return;
        mState = newState;
        Logger.d(TAG, "State → " + newState);
        if (mCallback != null) {
            try {
                mCallback.onStateChanged(newState);
            } catch (Exception e) {
                Logger.e(TAG, "Callback threw exception in onStateChanged", e);
            }
        }
    }

    private void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
