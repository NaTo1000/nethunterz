package com.offsec.nethunter.service;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import com.offsec.nethunter.MainActivity;
import com.offsec.nethunter.R;
import com.offsec.nethunter.utils.RootUtils;

/**
 * NethunterService - Long-running foreground service for the NetHunter application.
 *
 * <p>This service is responsible for orchestrating the core NetHunter functionality
 * in the background, including managing the Kali chroot environment, handling
 * network monitoring tasks, and maintaining the NetHunter daemon processes.</p>
 *
 * <p>The service exposes two public action constants:</p>
 * <ul>
 *   <li>{@link #ACTION_START} – Start / resume NetHunter operations</li>
 *   <li>{@link #ACTION_STOP}  – Gracefully stop NetHunter operations and the service</li>
 * </ul>
 *
 * <p>Example usage from an Activity:</p>
 * <pre>
 *   Intent i = new Intent(context, NethunterService.class);
 *   i.setAction(NethunterService.ACTION_START);
 *   context.startForegroundService(i);
 * </pre>
 */
public class NethunterService extends Service {

    private static final String TAG = "NethunterService";

    /** Action to start the NetHunter service. */
    public static final String ACTION_START = "com.offsec.nethunter.action.START";

    /** Action to stop the NetHunter service. */
    public static final String ACTION_STOP  = "com.offsec.nethunter.action.STOP";

    private static final String CHANNEL_ID    = "nethunter_service_channel";
    private static final int    NOTIFICATION_ID = 1001;

    private boolean isRunning = false;

    // -------------------------------------------------------------------------
    // Service lifecycle
    // -------------------------------------------------------------------------

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        Log.i(TAG, "NethunterService created");
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIFICATION_ID, buildNotification());

        String action = intent != null ? intent.getAction() : null;
        if (ACTION_STOP.equals(action)) {
            stopNethunter();
            stopSelf();
            return START_NOT_STICKY;
        }

        if (!isRunning) {
            startNethunter();
        }

        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        stopNethunter();
        Log.i(TAG, "NethunterService destroyed");
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    // -------------------------------------------------------------------------
    // Public control methods
    // -------------------------------------------------------------------------

    /**
     * Starts all NetHunter background operations.
     *
     * <p>Verifies root access is available before proceeding; logs a warning
     * and returns early if root is not accessible.</p>
     */
    public void startNethunter() {
        if (!RootUtils.isRootAvailable()) {
            Log.w(TAG, "Root is not available – cannot start NetHunter services");
            return;
        }

        Log.i(TAG, "Starting NetHunter services...");
        isRunning = true;

        // Mount the chroot filesystems
        RootUtils.executeCommand("mount -a");

        // Start any registered init.d scripts
        RootUtils.executeCommand("run-parts /data/local/nhsystem/etc/init.d");

        Log.i(TAG, "NetHunter services started");
    }

    /**
     * Stops all NetHunter background operations and unmounts the chroot
     * filesystems cleanly.
     */
    public void stopNethunter() {
        if (!isRunning) return;

        Log.i(TAG, "Stopping NetHunter services...");
        RootUtils.executeCommand("sync");
        RootUtils.executeCommand("umount -l /data/local/nhsystem/kali-arm64/proc");
        RootUtils.executeCommand("umount -l /data/local/nhsystem/kali-arm64/sys");
        RootUtils.executeCommand("umount -l /data/local/nhsystem/kali-arm64/dev/pts");
        RootUtils.executeCommand("umount -l /data/local/nhsystem/kali-arm64/dev");

        isRunning = false;
        Log.i(TAG, "NetHunter services stopped");
    }

    /**
     * Returns whether the service is currently running its background tasks.
     *
     * @return {@code true} if NetHunter operations are active
     */
    public boolean isRunning() {
        return isRunning;
    }

    // -------------------------------------------------------------------------
    // Notification helpers
    // -------------------------------------------------------------------------

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                getString(R.string.service_channel_name),
                NotificationManager.IMPORTANCE_LOW);
            channel.setDescription(getString(R.string.service_channel_description));
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    private Notification buildNotification() {
        Intent notifIntent = new Intent(this, MainActivity.class);
        int flags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
            ? PendingIntent.FLAG_IMMUTABLE : 0;
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 0, notifIntent, flags);

        Intent stopIntent = new Intent(this, NethunterService.class);
        stopIntent.setAction(ACTION_STOP);
        PendingIntent stopPendingIntent = PendingIntent.getService(this, 1, stopIntent, flags);

        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.service_notification_title))
            .setContentText(getString(R.string.service_notification_text))
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setContentIntent(pendingIntent)
            .addAction(android.R.drawable.ic_media_pause,
                getString(R.string.stop_service), stopPendingIntent)
            .setOngoing(true)
            .build();
    }
}
