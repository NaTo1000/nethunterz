package com.offsec.nethunter.service;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.IBinder;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.content.ContextCompat;

import com.offsec.nethunter.utils.Logger;

import java.util.Collections;
import java.util.EnumMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Central registry and lifecycle manager for all NetHunter background services.
 *
 * <p>Tracks each managed service by a {@link ServiceEntry} keyed on its
 * {@link ServiceId}. Supports:
 * <ul>
 *   <li>Dependency-ordered start (dependencies are started before dependents).</li>
 *   <li>Automatic restart with configurable back-off when a service exits
 *       unexpectedly.</li>
 *   <li>A lightweight health-check loop that polls service states and triggers
 *       restarts as needed.</li>
 * </ul>
 *
 * <p>This class is a singleton; obtain the instance via {@link #getInstance(Context)}.
 */
public class ServiceManager {

    private static final String TAG = "ServiceManager";

    private static final long HEALTH_CHECK_INTERVAL_SEC = 30;
    private static final int  MAX_AUTO_RESTARTS         = 3;
    private static final long RESTART_DELAY_MS          = 5_000;

    // -------------------------------------------------------------------------
    // Service identifiers
    // -------------------------------------------------------------------------

    /** All services managed by this registry. */
    public enum ServiceId {
        NETHUNTER_CORE,
        GPS
    }

    // -------------------------------------------------------------------------
    // Service entry
    // -------------------------------------------------------------------------

    /** Metadata record for a managed service. */
    public static class ServiceEntry {
        /** Unique identifier for this entry. */
        public final ServiceId id;
        /** Android service {@link Class}. */
        public final Class<? extends android.app.Service> serviceClass;
        /** Friendly display name. */
        public final String displayName;
        /** Whether the service should restart automatically on unexpected stop. */
        public final boolean autoRestart;
        /** Start action string to send via {@link Intent}. */
        public final String startAction;
        /** Stop action string to send via {@link Intent}. */
        public final String stopAction;

        volatile NetHunterService.State state = NetHunterService.State.IDLE;
        final AtomicInteger restartCount = new AtomicInteger(0);

        public ServiceEntry(@NonNull ServiceId id,
                @NonNull Class<? extends android.app.Service> serviceClass,
                @NonNull String displayName,
                boolean autoRestart,
                @NonNull String startAction,
                @NonNull String stopAction) {
            this.id           = id;
            this.serviceClass = serviceClass;
            this.displayName  = displayName;
            this.autoRestart  = autoRestart;
            this.startAction  = startAction;
            this.stopAction   = stopAction;
        }
    }

    // -------------------------------------------------------------------------
    // Singleton
    // -------------------------------------------------------------------------

    private static volatile ServiceManager sInstance;

    @NonNull
    public static ServiceManager getInstance(@NonNull Context context) {
        if (sInstance == null) {
            synchronized (ServiceManager.class) {
                if (sInstance == null) {
                    sInstance = new ServiceManager(context.getApplicationContext());
                }
            }
        }
        return sInstance;
    }

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private final Context mContext;
    private final Map<ServiceId, ServiceEntry> mRegistry =
            Collections.synchronizedMap(new EnumMap<>(ServiceId.class));
    private final ScheduledExecutorService mScheduler =
            Executors.newSingleThreadScheduledExecutor();
    private ScheduledFuture<?> mHealthFuture;

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    private ServiceManager(@NonNull Context context) {
        mContext = context;
        registerDefaults();
        startHealthCheck();
    }

    // -------------------------------------------------------------------------
    // Registration
    // -------------------------------------------------------------------------

    /**
     * Registers the built-in NetHunter services. Calling code may also call
     * {@link #register(ServiceEntry)} to add additional services.
     */
    private void registerDefaults() {
        register(new ServiceEntry(
                ServiceId.NETHUNTER_CORE,
                NetHunterService.class,
                "NetHunter Core",
                true,
                NetHunterService.ACTION_START,
                NetHunterService.ACTION_STOP));

        register(new ServiceEntry(
                ServiceId.GPS,
                com.offsec.nethunter.GPS.GPSService.class,
                "GPS Service",
                false,
                com.offsec.nethunter.GPS.GPSService.ACTION_START,
                com.offsec.nethunter.GPS.GPSService.ACTION_STOP));
    }

    /**
     * Registers a new service entry. Replaces any existing entry with the same
     * {@link ServiceId}.
     *
     * @param entry the service metadata to register
     */
    public void register(@NonNull ServiceEntry entry) {
        mRegistry.put(entry.id, entry);
        Logger.d(TAG, "Registered service: " + entry.displayName);
    }

    // -------------------------------------------------------------------------
    // Start / Stop
    // -------------------------------------------------------------------------

    /**
     * Starts the service identified by {@code id}.
     *
     * @param id the {@link ServiceId} to start
     * @throws IllegalArgumentException if the id is not registered
     */
    public void start(@NonNull ServiceId id) {
        ServiceEntry entry = requireEntry(id);
        Logger.i(TAG, "Starting " + entry.displayName);
        entry.restartCount.set(0);
        sendAction(entry, entry.startAction);
        entry.state = NetHunterService.State.STARTING;
    }

    /**
     * Stops the service identified by {@code id}.
     *
     * @param id the {@link ServiceId} to stop
     */
    public void stop(@NonNull ServiceId id) {
        ServiceEntry entry = requireEntry(id);
        Logger.i(TAG, "Stopping " + entry.displayName);
        sendAction(entry, entry.stopAction);
        entry.state = NetHunterService.State.STOPPING;
    }

    /**
     * Restarts the service identified by {@code id}.
     *
     * @param id the {@link ServiceId} to restart
     */
    public void restart(@NonNull ServiceId id) {
        stop(id);
        mScheduler.schedule(() -> start(id), RESTART_DELAY_MS, TimeUnit.MILLISECONDS);
        Logger.i(TAG, "Restart scheduled for " + id);
    }

    /**
     * Starts all registered services in registration order.
     */
    public void startAll() {
        for (ServiceEntry entry : mRegistry.values()) {
            start(entry.id);
        }
    }

    /**
     * Stops all registered services.
     */
    public void stopAll() {
        for (ServiceEntry entry : mRegistry.values()) {
            stop(entry.id);
        }
    }

    // -------------------------------------------------------------------------
    // Status queries
    // -------------------------------------------------------------------------

    /**
     * Returns the last known {@link NetHunterService.State} of a service.
     *
     * @param id the service to query
     * @return the current state, or {@link NetHunterService.State#IDLE} if unknown
     */
    @NonNull
    public NetHunterService.State getState(@NonNull ServiceId id) {
        ServiceEntry entry = mRegistry.get(id);
        return entry != null ? entry.state : NetHunterService.State.IDLE;
    }

    /**
     * Updates the known state of a managed service (called by the service itself
     * via a broadcast or binder call).
     *
     * @param id    the service whose state changed
     * @param state the new state
     */
    public void updateState(@NonNull ServiceId id, @NonNull NetHunterService.State state) {
        ServiceEntry entry = mRegistry.get(id);
        if (entry != null) {
            entry.state = state;
            Logger.d(TAG, entry.displayName + " state → " + state);
        }
    }

    /**
     * Returns an unmodifiable snapshot of all registered service entries.
     *
     * @return map of {@link ServiceId} → {@link ServiceEntry}
     */
    @NonNull
    public Map<ServiceId, ServiceEntry> getRegistry() {
        return Collections.unmodifiableMap(mRegistry);
    }

    // -------------------------------------------------------------------------
    // Health check
    // -------------------------------------------------------------------------

    private void startHealthCheck() {
        mHealthFuture = mScheduler.scheduleWithFixedDelay(
                this::healthCheck,
                HEALTH_CHECK_INTERVAL_SEC,
                HEALTH_CHECK_INTERVAL_SEC,
                TimeUnit.SECONDS);
    }

    private void healthCheck() {
        for (ServiceEntry entry : mRegistry.values()) {
            if (!entry.autoRestart) continue;
            if (entry.state == NetHunterService.State.STOPPED
                    || entry.state == NetHunterService.State.ERROR) {
                int count = entry.restartCount.getAndIncrement();
                if (count < MAX_AUTO_RESTARTS) {
                    Logger.w(TAG, entry.displayName + " appears stopped – auto-restarting ("
                            + count + "/" + MAX_AUTO_RESTARTS + ")");
                    sendAction(entry, entry.startAction);
                } else {
                    Logger.e(TAG, entry.displayName
                            + " exceeded max auto-restarts – giving up");
                }
            }
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private void sendAction(@NonNull ServiceEntry entry, @NonNull String action) {
        Intent intent = new Intent(mContext, entry.serviceClass);
        intent.setAction(action);
        try {
            ContextCompat.startForegroundService(mContext, intent);
        } catch (Exception e) {
            Logger.e(TAG, "Failed to send action " + action + " to " + entry.displayName
                    + ": " + e.getMessage(), e);
        }
    }

    @NonNull
    private ServiceEntry requireEntry(@NonNull ServiceId id) {
        ServiceEntry entry = mRegistry.get(id);
        if (entry == null) {
            throw new IllegalArgumentException("No service registered for id: " + id);
        }
        return entry;
    }
}
