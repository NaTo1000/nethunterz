package com.offsec.nethunter.GPS;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationManager;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.app.ActivityCompat;
import androidx.core.app.NotificationCompat;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;

import com.offsec.nethunter.MainActivity;
import com.offsec.nethunter.R;
import com.offsec.nethunter.utils.Logger;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.Socket;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Foreground service that connects to a GPS daemon (gpsd / mock socket), reads
 * NMEA sentences, and broadcasts parsed location updates via
 * {@link LocalBroadcastManager}.
 *
 * <p>When a valid fix is available the service optionally injects a mock
 * {@link Location} through the {@link LocationManager} so other apps can use the
 * GPS data even when hardware GPS is unavailable.
 */
public class GPSService extends Service {

    private static final String TAG = "GPSService";

    // -------------------------------------------------------------------------
    // Constants
    // -------------------------------------------------------------------------

    public static final String ACTION_START      = "com.offsec.nethunter.GPS.START";
    public static final String ACTION_STOP       = "com.offsec.nethunter.GPS.STOP";
    public static final String ACTION_GPS_UPDATE = "com.offsec.nethunter.GPS.UPDATE";

    public static final String EXTRA_LATITUDE    = "lat";
    public static final String EXTRA_LONGITUDE   = "lon";
    public static final String EXTRA_ALTITUDE    = "alt";
    public static final String EXTRA_SPEED       = "speed";
    public static final String EXTRA_SATELLITES  = "sats";
    public static final String EXTRA_FIX_TYPE    = "fixType";
    public static final String EXTRA_RAW_NMEA    = "rawNmea";

    private static final String CHANNEL_ID      = "gps_service_channel";
    private static final int    NOTIFICATION_ID = 1001;

    private static final String GPS_HOST        = "127.0.0.1";
    private static final int    GPS_PORT        = 2947;
    private static final int    RECONNECT_DELAY = 3000; // ms
    private static final int    MAX_RETRIES     = 5;

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private final AtomicBoolean mRunning  = new AtomicBoolean(false);
    private final AtomicBoolean mStopping = new AtomicBoolean(false);

    private ExecutorService  mExecutor;
    private PowerManager.WakeLock mWakeLock;
    private NMEAParser        mParser;
    private LocationManager   mLocationManager;
    private boolean           mMockLocationEnabled;

    // -------------------------------------------------------------------------
    // Service lifecycle
    // -------------------------------------------------------------------------

    @Override
    public void onCreate() {
        super.onCreate();
        mParser          = new NMEAParser();
        mLocationManager = (LocationManager) getSystemService(LOCATION_SERVICE);
        mExecutor        = Executors.newSingleThreadExecutor();

        mParser.addCallback(this::onNMEADataUpdated);
        createNotificationChannel();
        acquireWakeLock();
        Logger.i(TAG, "GPSService created");
    }

    @Override
    public int onStartCommand(@Nullable Intent intent, int flags, int startId) {
        if (intent == null) return START_STICKY;

        String action = intent.getAction();
        if (ACTION_START.equals(action)) {
            if (!mRunning.get()) {
                startForeground(NOTIFICATION_ID, buildNotification("Connecting…"));
                mStopping.set(false);
                mExecutor.submit(this::runNMEALoop);
                Logger.i(TAG, "GPS service started");
            }
        } else if (ACTION_STOP.equals(action)) {
            stopSelf();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        mStopping.set(true);
        mRunning.set(false);
        releaseWakeLock();
        disableMockLocation();
        if (mExecutor != null) {
            mExecutor.shutdownNow();
        }
        Logger.i(TAG, "GPSService destroyed");
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(@NonNull Intent intent) {
        return null;
    }

    // -------------------------------------------------------------------------
    // NMEA reading loop
    // -------------------------------------------------------------------------

    /**
     * Long-running loop executed on a background thread. Attempts to connect to
     * the GPS daemon socket and reads NMEA sentences until the service is stopped.
     * Retries with back-off on connection failure.
     */
    private void runNMEALoop() {
        int retries = 0;
        mRunning.set(true);

        while (!mStopping.get() && retries < MAX_RETRIES) {
            try (Socket socket = new Socket(GPS_HOST, GPS_PORT);
                 BufferedReader reader = new BufferedReader(
                         new InputStreamReader(socket.getInputStream()))) {

                retries = 0;
                updateNotification("Connected – reading NMEA");
                Logger.i(TAG, "Connected to GPS daemon at " + GPS_HOST + ":" + GPS_PORT);

                String line;
                while (!mStopping.get() && (line = reader.readLine()) != null) {
                    if (!line.isEmpty()) {
                        mParser.parse(line);
                    }
                }
            } catch (IOException e) {
                if (!mStopping.get()) {
                    retries++;
                    Logger.w(TAG, "GPS socket error (retry " + retries + "/" + MAX_RETRIES
                            + "): " + e.getMessage());
                    updateNotification("Reconnecting… (" + retries + ")");
                    sleep(RECONNECT_DELAY);
                }
            }
        }

        if (retries >= MAX_RETRIES) {
            Logger.e(TAG, "Max retries reached – GPS daemon unavailable");
            updateNotification("GPS daemon unavailable");
        }
        mRunning.set(false);
    }

    // -------------------------------------------------------------------------
    // NMEA data callback
    // -------------------------------------------------------------------------

    private void onNMEADataUpdated(@NonNull NMEAParser.NMEAData data) {
        // Broadcast to UI
        Intent broadcast = new Intent(ACTION_GPS_UPDATE);
        broadcast.putExtra(EXTRA_LATITUDE,   data.latitude);
        broadcast.putExtra(EXTRA_LONGITUDE,  data.longitude);
        broadcast.putExtra(EXTRA_ALTITUDE,   data.altitude);
        broadcast.putExtra(EXTRA_SPEED,      data.speedKmh);
        broadcast.putExtra(EXTRA_SATELLITES, data.satellitesUsed);
        broadcast.putExtra(EXTRA_FIX_TYPE,   data.fixType);
        broadcast.putExtra(EXTRA_RAW_NMEA,   data.lastSentence);
        LocalBroadcastManager.getInstance(this).sendBroadcast(broadcast);

        // Inject mock location if we have a valid fix
        if (data.fixQuality > 0) {
            injectMockLocation(data);
        }
    }

    // -------------------------------------------------------------------------
    // Mock location injection
    // -------------------------------------------------------------------------

    /**
     * Injects a mock {@link Location} into {@link LocationManager} so that
     * applications relying on the system location provider can consume the data.
     *
     * <p>Requires the {@code ACCESS_MOCK_LOCATION} permission and the device
     * developer option "Allow mock locations" (or the app to be set as the mock
     * location provider in settings).
     */
    private void injectMockLocation(@NonNull NMEAParser.NMEAData data) {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        try {
            if (!mMockLocationEnabled) {
                mLocationManager.addTestProvider(
                        LocationManager.GPS_PROVIDER,
                        false, false, false, false, true, true, true,
                        android.location.Criteria.POWER_LOW,
                        android.location.Criteria.ACCURACY_FINE);
                mLocationManager.setTestProviderEnabled(LocationManager.GPS_PROVIDER, true);
                mMockLocationEnabled = true;
            }
            Location loc = new Location(LocationManager.GPS_PROVIDER);
            loc.setLatitude(data.latitude);
            loc.setLongitude(data.longitude);
            loc.setAltitude(data.altitude);
            loc.setSpeed(data.speedKmh / 3.6f);
            loc.setBearing(data.heading);
            loc.setAccuracy(data.hdop > 0 ? data.hdop * 5 : 5.0f);
            loc.setTime(System.currentTimeMillis());
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR1) {
                loc.setElapsedRealtimeNanos(SystemClock.elapsedRealtimeNanos());
            }
            mLocationManager.setTestProviderLocation(LocationManager.GPS_PROVIDER, loc);
        } catch (Exception e) {
            Logger.w(TAG, "Mock location injection failed: " + e.getMessage());
            mMockLocationEnabled = false;
        }
    }

    private void disableMockLocation() {
        if (!mMockLocationEnabled) return;
        try {
            mLocationManager.removeTestProvider(LocationManager.GPS_PROVIDER);
        } catch (Exception ignored) {
        }
        mMockLocationEnabled = false;
    }

    // -------------------------------------------------------------------------
    // Notification helpers
    // -------------------------------------------------------------------------

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "GPS Service", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("NetHunter GPS foreground service");
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    @NonNull
    private Notification buildNotification(@NonNull String status) {
        Intent intent = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent,
                PendingIntent.FLAG_IMMUTABLE);

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("NetHunter GPS")
                .setContentText(status)
                .setSmallIcon(R.drawable.ic_gps)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }

    private void updateNotification(@NonNull String status) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(NOTIFICATION_ID, buildNotification(status));
    }

    // -------------------------------------------------------------------------
    // Wake lock helpers
    // -------------------------------------------------------------------------

    private void acquireWakeLock() {
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm != null) {
            mWakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, TAG + ":WakeLock");
            mWakeLock.acquire(10 * 60 * 1000L); // max 10 minutes per acquisition
        }
    }

    private void releaseWakeLock() {
        if (mWakeLock != null && mWakeLock.isHeld()) {
            mWakeLock.release();
        }
    }

    // -------------------------------------------------------------------------
    // Utility
    // -------------------------------------------------------------------------

    private void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
