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
import android.os.PowerManager;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import com.offsec.nethunter.MainActivity;
import com.offsec.nethunter.R;
import com.offsec.nethunter.utils.Logger;
import com.offsec.nethunter.utils.NetHunterPaths;
import com.offsec.nethunter.utils.ShellExecutor;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Core NetHunter foreground service.
 *
 * <p>Responsibilities:
 * <ul>
 *   <li>Mounts/unmounts the Kali chroot environment via shell commands.</li>
 *   <li>Processes a serialised shell-command queue so that callers do not need to
 *       manage threading themselves.</li>
 *   <li>Holds a partial {@link PowerManager.WakeLock} to keep the CPU alive while
 *       long-running security tools are active.</li>
 *   <li>Exposes a {@link LocalBinder} so bound clients can interact synchronously.</li>
 * </ul>
 */
public class NetHunterService extends Service {

    private static final String TAG = "NetHunterService";

    // -------------------------------------------------------------------------
    // Intent actions
    // -------------------------------------------------------------------------

    public static final String ACTION_START   = "com.offsec.nethunter.service.START";
    public static final String ACTION_STOP    = "com.offsec.nethunter.service.STOP";
    public static final String ACTION_RESTART = "com.offsec.nethunter.service.RESTART";

    // -------------------------------------------------------------------------
    // Service state
    // -------------------------------------------------------------------------

    /** Observable service states. */
    public enum State {
        IDLE,
        STARTING,
        RUNNING,
        STOPPING,
        STOPPED,
        ERROR
    }

    // -------------------------------------------------------------------------
    // Constants
    // -------------------------------------------------------------------------

    private static final String CHANNEL_ID      = "nethunter_service_channel";
    private static final int    NOTIFICATION_ID = 1000;

    // -------------------------------------------------------------------------
    // Fields
    // -------------------------------------------------------------------------

    private final IBinder         mBinder       = new LocalBinder();
    private final AtomicBoolean   mRunning      = new AtomicBoolean(false);
    private final AtomicReference<State> mState = new AtomicReference<>(State.IDLE);
    private final BlockingQueue<Runnable> mCommandQueue = new LinkedBlockingQueue<>();

    private ExecutorService   mExecutor;
    private PowerManager.WakeLock mWakeLock;
    private ShellExecutor     mShell;
    private boolean           mChrootMounted;

    // -------------------------------------------------------------------------
    // Binder
    // -------------------------------------------------------------------------

    /** Allows bound clients to obtain a reference to this service instance. */
    public class LocalBinder extends Binder {
        @NonNull
        public NetHunterService getService() {
            return NetHunterService.this;
        }
    }

    // -------------------------------------------------------------------------
    // Lifecycle
    // -------------------------------------------------------------------------

    @Override
    public void onCreate() {
        super.onCreate();
        mShell    = ShellExecutor.getInstance();
        mExecutor = Executors.newSingleThreadExecutor();
        createNotificationChannel();
        acquireWakeLock();
        Logger.i(TAG, "NetHunterService created");
    }

    @Override
    public int onStartCommand(@Nullable Intent intent, int flags, int startId) {
        if (intent == null) {
            return START_STICKY;
        }
        String action = intent.getAction();
        if (action == null) return START_STICKY;

        switch (action) {
            case ACTION_START:
                if (!mRunning.get()) {
                    startForeground(NOTIFICATION_ID, buildNotification("Starting…"));
                    mExecutor.submit(this::doStart);
                }
                break;

            case ACTION_STOP:
                mExecutor.submit(this::doStop);
                break;

            case ACTION_RESTART:
                mExecutor.submit(() -> {
                    doStop();
                    doStart();
                });
                break;

            default:
                Logger.w(TAG, "Unknown action: " + action);
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        mRunning.set(false);
        releaseWakeLock();
        if (mExecutor != null) mExecutor.shutdownNow();
        Logger.i(TAG, "NetHunterService destroyed");
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(@NonNull Intent intent) {
        return mBinder;
    }

    // -------------------------------------------------------------------------
    // Public API (callable via binder)
    // -------------------------------------------------------------------------

    /**
     * Enqueues a shell command for execution on the service's worker thread.
     *
     * @param command  the shell command string
     * @param callback optional callback for output/completion events
     */
    public void enqueueCommand(@NonNull String command,
            @Nullable ShellExecutor.Callback callback) {
        mCommandQueue.offer(() -> mShell.executeAsync(command, callback));
        Logger.d(TAG, "Command enqueued: " + command);
    }

    /**
     * Returns the current service state.
     *
     * @return current {@link State}
     */
    @NonNull
    public State getServiceState() {
        return mState.get();
    }

    /**
     * Returns {@code true} if the Kali chroot is currently mounted.
     */
    public boolean isChrootMounted() {
        return mChrootMounted;
    }

    // -------------------------------------------------------------------------
    // Start / Stop logic
    // -------------------------------------------------------------------------

    private void doStart() {
        setState(State.STARTING);
        updateNotification("Mounting chroot…");
        Logger.i(TAG, "Starting NetHunter core");

        try {
            mountChroot();
            startInitScripts();
            mRunning.set(true);
            setState(State.RUNNING);
            updateNotification("Running");
            Logger.i(TAG, "NetHunter service running");
            processCommandQueue();
        } catch (Exception e) {
            Logger.e(TAG, "Service start failed: " + e.getMessage(), e);
            setState(State.ERROR);
            updateNotification("Error – check logs");
        }
    }

    private void doStop() {
        setState(State.STOPPING);
        updateNotification("Stopping…");
        Logger.i(TAG, "Stopping NetHunter core");
        mRunning.set(false);

        try {
            stopServices();
            unmountChroot();
            setState(State.STOPPED);
            updateNotification("Stopped");
            Logger.i(TAG, "NetHunter service stopped cleanly");
        } catch (Exception e) {
            Logger.e(TAG, "Error during stop: " + e.getMessage(), e);
            setState(State.ERROR);
        }
        stopForeground(true);
        stopSelf();
    }

    // -------------------------------------------------------------------------
    // Chroot management
    // -------------------------------------------------------------------------

    /**
     * Mounts the Kali chroot by executing the bootkali script.
     * Binds {@code /proc}, {@code /sys}, {@code /dev}, and {@code /dev/pts}
     * inside the chroot root.
     */
    private void mountChroot() {
        if (mChrootMounted) {
            Logger.d(TAG, "Chroot already mounted");
            return;
        }
        String chrootPath = NetHunterPaths.getChrootPath();
        String[] cmds = {
            "mount -o bind /proc "    + chrootPath + "/proc",
            "mount -o bind /sys "     + chrootPath + "/sys",
            "mount -o bind /dev "     + chrootPath + "/dev",
            "mount -o bind /dev/pts " + chrootPath + "/dev/pts"
        };
        for (String cmd : cmds) {
            int exitCode = mShell.executeSync(cmd);
            if (exitCode != 0) {
                Logger.w(TAG, "Mount command returned " + exitCode + ": " + cmd);
            }
        }
        mChrootMounted = true;
        Logger.i(TAG, "Chroot mounted at " + chrootPath);
    }

    /**
     * Unmounts all bind-mounted directories inside the chroot in reverse order.
     */
    private void unmountChroot() {
        if (!mChrootMounted) return;
        String chrootPath = NetHunterPaths.getChrootPath();
        String[] cmds = {
            "umount " + chrootPath + "/dev/pts",
            "umount " + chrootPath + "/dev",
            "umount " + chrootPath + "/sys",
            "umount " + chrootPath + "/proc"
        };
        for (String cmd : cmds) {
            int exitCode = mShell.executeSync(cmd);
            if (exitCode != 0) {
                Logger.w(TAG, "Umount returned " + exitCode + ": " + cmd);
            }
        }
        mChrootMounted = false;
        Logger.i(TAG, "Chroot unmounted");
    }

    // -------------------------------------------------------------------------
    // Init scripts
    // -------------------------------------------------------------------------

    private void startInitScripts() {
        String initD = NetHunterPaths.getChrootPath() + "/etc/init.d";
        int code = mShell.executeSync(
                "chroot " + NetHunterPaths.getChrootPath()
                + " /bin/bash -c 'run-parts /etc/init.d' 2>&1");
        Logger.d(TAG, "Init scripts exit code: " + code);
    }

    private void stopServices() {
        int code = mShell.executeSync(
                "chroot " + NetHunterPaths.getChrootPath()
                + " /bin/bash -c 'service --status-all 2>/dev/null; killall -q dbus-daemon' 2>&1");
        Logger.d(TAG, "Service stop exit code: " + code);
    }

    // -------------------------------------------------------------------------
    // Command queue
    // -------------------------------------------------------------------------

    /** Drains the command queue until the service is stopped. */
    private void processCommandQueue() {
        while (mRunning.get()) {
            try {
                Runnable task = mCommandQueue.poll(1, java.util.concurrent.TimeUnit.SECONDS);
                if (task != null) task.run();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }

    // -------------------------------------------------------------------------
    // Notification
    // -------------------------------------------------------------------------

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID, "NetHunter Service", NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("NetHunter core foreground service");
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(ch);
        }
    }

    @NonNull
    private Notification buildNotification(@NonNull String status) {
        Intent intent = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent,
                PendingIntent.FLAG_IMMUTABLE);

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("NetHunter")
                .setContentText(status)
                .setSmallIcon(R.drawable.ic_service)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }

    private void updateNotification(@NonNull String status) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(NOTIFICATION_ID, buildNotification(status));
    }

    // -------------------------------------------------------------------------
    // State management
    // -------------------------------------------------------------------------

    private void setState(@NonNull State newState) {
        mState.set(newState);
        Logger.d(TAG, "State → " + newState);
    }

    // -------------------------------------------------------------------------
    // Wake lock
    // -------------------------------------------------------------------------

    private void acquireWakeLock() {
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm != null) {
            mWakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, TAG + ":WakeLock");
            mWakeLock.acquire(30 * 60 * 1000L); // max 30 minutes
        }
    }

    private void releaseWakeLock() {
        if (mWakeLock != null && mWakeLock.isHeld()) {
            mWakeLock.release();
        }
    }
}
