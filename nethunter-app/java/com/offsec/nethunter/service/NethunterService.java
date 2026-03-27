package com.offsec.nethunter.service;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Binder;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import com.offsec.nethunter.MainActivity;
import com.offsec.nethunter.R;
import com.offsec.nethunter.flipper.FlipperManager;
import com.offsec.nethunter.GPS.NMEAParser;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Foreground service that manages the core NetHunter subsystems:
 * chroot environment, GPS listener, and Flipper Zero connections.
 */
public class NethunterService extends Service {

    private static final String TAG = "NethunterService";

    public static final String ACTION_START_SERVICE  = "com.offsec.nethunter.action.START_SERVICE";
    public static final String ACTION_STOP_SERVICE   = "com.offsec.nethunter.action.STOP_SERVICE";
    public static final String EXTRA_SOURCE          = "extra_source";

    private static final String NOTIFICATION_CHANNEL_ID   = "nethunter_service_channel";
    private static final String NOTIFICATION_CHANNEL_NAME = "NetHunter Service";
    private static final int    NOTIFICATION_ID            = 1001;

    private final IBinder binder = new LocalBinder();
    private final AtomicBoolean running = new AtomicBoolean(false);

    private ExecutorService workerExecutor;
    private ScheduledExecutorService scheduledExecutor;

    private FlipperManager flipperManager;
    private NMEAParser nmeaParser;

    // Service state
    private boolean chrootRunning = false;
    private boolean gpsActive     = false;
    private boolean flipperActive = false;

    public class LocalBinder extends Binder {
        public NethunterService getService() {
            return NethunterService.this;
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "NethunterService created");
        workerExecutor = Executors.newFixedThreadPool(4);
        scheduledExecutor = Executors.newScheduledThreadPool(2);
        nmeaParser = new NMEAParser();
        flipperManager = new FlipperManager(this);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) {
            Log.w(TAG, "Null intent received, restarting service");
            startForegroundNotification();
            return START_STICKY;
        }

        String action = intent.getAction();
        String source = intent.getStringExtra(EXTRA_SOURCE);
        Log.d(TAG, "onStartCommand action=" + action + " source=" + source);

        if (ACTION_STOP_SERVICE.equals(action)) {
            stopSelf();
            return START_NOT_STICKY;
        }

        startForegroundNotification();

        if (!running.getAndSet(true)) {
            workerExecutor.submit(this::initializeSubsystems);
        }

        return START_STICKY;
    }

    private void initializeSubsystems() {
        Log.i(TAG, "Initializing NetHunter subsystems");

        // Check if chroot environment is available
        checkChrootEnvironment();

        // Start GPS monitoring
        initializeGPS();

        // Try to connect to Flipper if USB is available
        scheduleFlipperConnectionAttempt();

        Log.i(TAG, "Subsystem initialization complete");
    }

    private void checkChrootEnvironment() {
        try {
            Process process = Runtime.getRuntime().exec(new String[]{"su", "-c",
                "test -d /data/local/nhsystem/kali-arm64 && echo FOUND || echo MISSING"});
            byte[] buffer = new byte[256];
            int len = process.getInputStream().read(buffer);
            String result = new String(buffer, 0, len).trim();
            chrootRunning = "FOUND".equals(result);
            Log.i(TAG, "Chroot environment: " + (chrootRunning ? "found" : "not found"));
        } catch (Exception e) {
            Log.w(TAG, "Could not check chroot environment: " + e.getMessage());
            chrootRunning = false;
        }
    }

    private void initializeGPS() {
        nmeaParser.addListener("service", new NMEAParser.NMEAListener() {
            @Override
            public void onGGAParsed(double lat, double lon, double alt, int fixQuality, int numSats) {
                gpsActive = true;
                Log.d(TAG, String.format("GPS fix: %.6f, %.6f alt=%.1fm sats=%d", lat, lon, alt, numSats));
            }
            @Override
            public void onRMCParsed(double lat, double lon, double speed, double bearing, String utcTime) {
                Log.d(TAG, String.format("GPS RMC: %.6f, %.6f spd=%.1f brg=%.1f", lat, lon, speed, bearing));
            }
            @Override
            public void onParseError(String sentence, String error) {
                Log.w(TAG, "NMEA parse error: " + error + " in: " + sentence);
            }
        });
        Log.i(TAG, "GPS NMEA parser initialized");
    }

    private void scheduleFlipperConnectionAttempt() {
        scheduledExecutor.scheduleWithFixedDelay(() -> {
            if (!flipperActive && flipperManager != null) {
                try {
                    flipperActive = flipperManager.tryAutoConnect();
                    if (flipperActive) {
                        Log.i(TAG, "Flipper Zero connected automatically");
                        updateNotification("Flipper Zero connected");
                    }
                } catch (Exception e) {
                    Log.d(TAG, "Flipper auto-connect attempt failed: " + e.getMessage());
                }
            }
        }, 5, 30, TimeUnit.SECONDS);
    }

    private void startForegroundNotification() {
        Notification notification = buildNotification("NetHunter service running");
        startForeground(NOTIFICATION_ID, notification);
    }

    private void updateNotification(String status) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) {
            nm.notify(NOTIFICATION_ID, buildNotification(status));
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                NOTIFICATION_CHANNEL_NAME,
                NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("NetHunter background service");
            channel.setShowBadge(false);
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    private Notification buildNotification(String statusText) {
        Intent notificationIntent = new Intent(this, MainActivity.class);
        notificationIntent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        int pendingFlags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
            ? PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
            : PendingIntent.FLAG_UPDATE_CURRENT;
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 0, notificationIntent, pendingFlags);

        Intent stopIntent = new Intent(this, NethunterService.class);
        stopIntent.setAction(ACTION_STOP_SERVICE);
        PendingIntent stopPending = PendingIntent.getService(this, 1, stopIntent, pendingFlags);

        return new NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(statusText)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .addAction(R.drawable.ic_stop, "Stop", stopPending)
            .build();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return binder;
    }

    @Override
    public void onDestroy() {
        Log.i(TAG, "NethunterService destroying");
        running.set(false);

        if (flipperManager != null) {
            flipperManager.disconnect();
        }

        if (scheduledExecutor != null) {
            scheduledExecutor.shutdownNow();
        }
        if (workerExecutor != null) {
            workerExecutor.shutdownNow();
        }

        stopForeground(true);
        super.onDestroy();
    }

    // Public API for bound clients
    public boolean isChrootRunning()  { return chrootRunning; }
    public boolean isGpsActive()      { return gpsActive; }
    public boolean isFlipperActive()  { return flipperActive; }
    public NMEAParser getNmeaParser() { return nmeaParser; }
    public FlipperManager getFlipperManager() { return flipperManager; }
}
