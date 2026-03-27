package com.offsec.nethunter.GPS;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.location.LocationManager;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import com.offsec.nethunter.MainActivity;
import com.offsec.nethunter.R;
import com.offsec.nethunter.utils.NethunterPaths;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;

/**
 * GpsService - A foreground service that streams NMEA GPS data into the Kali chroot.
 *
 * <p>The service registers an {@link NMEAHandler} as both a {@link android.location.GpsStatus.NmeaListener}
 * and a {@link android.location.LocationListener} via the system {@link LocationManager}.
 * Each NMEA sentence received is written to a named pipe (FIFO) located at
 * {@link NethunterPaths#GPS_SOCKET_PATH}, allowing GPS-aware tools inside the chroot
 * (e.g., gpsd) to consume the data in real time.</p>
 *
 * <p>Usage:</p>
 * <pre>
 *   Intent intent = new Intent(context, GpsService.class);
 *   context.startForegroundService(intent);
 * </pre>
 */
public class GpsService extends Service implements NMEAHandler.NMEAListener {

    private static final String TAG = "GpsService";
    private static final String CHANNEL_ID = "nethunter_gps_channel";
    private static final int NOTIFICATION_ID = 2001;
    private static final long GPS_MIN_TIME_MS = 1000L;
    private static final float GPS_MIN_DIST_M = 0.0f;

    private LocationManager locationManager;
    private NMEAHandler nmeaHandler;
    private OutputStream nmeaOutputStream;
    private boolean isRunning = false;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        locationManager = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
        nmeaHandler = new NMEAHandler(this);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIFICATION_ID, buildNotification());
        if (!isRunning) {
            startGps();
            isRunning = true;
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        stopGps();
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    // -------------------------------------------------------------------------
    // NMEAHandler.NMEAListener
    // -------------------------------------------------------------------------

    @Override
    public void onNmeaSentence(String sentence) {
        writeNmea(sentence);
    }

    // -------------------------------------------------------------------------
    // Internal helpers
    // -------------------------------------------------------------------------

    /**
     * Registers GPS listeners with the {@link LocationManager}.
     * Requires {@code ACCESS_FINE_LOCATION} permission granted at runtime.
     */
    @SuppressWarnings("MissingPermission")
    private void startGps() {
        try {
            openNmeaStream();
            locationManager.requestLocationUpdates(
                LocationManager.GPS_PROVIDER,
                GPS_MIN_TIME_MS,
                GPS_MIN_DIST_M,
                nmeaHandler);
            locationManager.addNmeaListener(nmeaHandler);
            Log.i(TAG, "GPS listeners registered");
        } catch (SecurityException e) {
            Log.e(TAG, "Location permission not granted", e);
            stopSelf();
        }
    }

    /** Removes GPS listeners and closes the NMEA output stream. */
    private void stopGps() {
        try {
            locationManager.removeUpdates(nmeaHandler);
            locationManager.removeNmeaListener(nmeaHandler);
        } catch (Exception e) {
            Log.w(TAG, "Error removing GPS listeners", e);
        }
        closeNmeaStream();
        isRunning = false;
        Log.i(TAG, "GPS service stopped");
    }

    /**
     * Opens the NMEA output stream to the chroot FIFO / socket file.
     * Creates the file if it does not yet exist.
     */
    private void openNmeaStream() {
        try {
            File nmeaFile = new File(NethunterPaths.GPS_SOCKET_PATH);
            File parent = nmeaFile.getParentFile();
            if (parent != null && !parent.exists()) {
                parent.mkdirs();
            }
            nmeaOutputStream = new FileOutputStream(nmeaFile, false);
            Log.i(TAG, "NMEA output stream opened: " + NethunterPaths.GPS_SOCKET_PATH);
        } catch (IOException e) {
            Log.e(TAG, "Failed to open NMEA output stream", e);
            nmeaOutputStream = null;
        }
    }

    /** Closes the NMEA output stream, suppressing any {@link IOException}. */
    private void closeNmeaStream() {
        if (nmeaOutputStream != null) {
            try {
                nmeaOutputStream.close();
            } catch (IOException ignored) {
            } finally {
                nmeaOutputStream = null;
            }
        }
    }

    /**
     * Writes an NMEA sentence to the output stream.
     *
     * @param sentence the NMEA sentence to write (should include CRLF terminator)
     */
    private void writeNmea(String sentence) {
        if (nmeaOutputStream == null || sentence == null) return;
        try {
            nmeaOutputStream.write(sentence.getBytes("ASCII"));
            nmeaOutputStream.flush();
        } catch (IOException e) {
            Log.w(TAG, "Failed to write NMEA sentence", e);
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                getString(R.string.gps_channel_name),
                NotificationManager.IMPORTANCE_LOW);
            channel.setDescription(getString(R.string.gps_channel_description));
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    private Notification buildNotification() {
        Intent notifIntent = new Intent(this, MainActivity.class);
        int flags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
            ? PendingIntent.FLAG_IMMUTABLE : 0;
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 0, notifIntent, flags);

        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.gps_service_title))
            .setContentText(getString(R.string.gps_service_text))
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build();
    }
}
