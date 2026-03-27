package com.offsec.nethunter.updateReceiver;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import androidx.core.content.ContextCompat;

import com.offsec.nethunter.service.NetHunterService;
import com.offsec.nethunter.utils.FileManager;
import com.offsec.nethunter.utils.Logger;

/**
 * {@link BroadcastReceiver} that handles {@link Intent#ACTION_MY_PACKAGE_REPLACED}
 * (and the system-wide {@link Intent#ACTION_PACKAGE_REPLACED}) to re-initialise
 * NetHunter after a self-update.
 *
 * <p>On receipt the receiver:
 * <ol>
 *   <li>Re-extracts updated asset files so scripts and configs stay current.</li>
 *   <li>Requests the {@link NetHunterService} to perform a soft restart so it
 *       picks up any new binaries without requiring a device reboot.</li>
 * </ol>
 */
public class UpdateReceiver extends BroadcastReceiver {

    private static final String TAG = "UpdateReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        if (action == null) return;

        boolean selfUpdate = Intent.ACTION_MY_PACKAGE_REPLACED.equals(action);
        boolean pkgReplaced = Intent.ACTION_PACKAGE_REPLACED.equals(action);

        if (!selfUpdate && !pkgReplaced) return;

        // For ACTION_PACKAGE_REPLACED, verify the package matches ours
        if (pkgReplaced) {
            String pkg = intent.getData() != null ? intent.getData().getSchemeSpecificPart() : null;
            if (!context.getPackageName().equals(pkg)) return;
        }

        Logger.i(TAG, "Package replaced – re-initialising NetHunter");

        // Re-extract updated assets on a background thread to avoid ANR
        new Thread(() -> {
            try {
                FileManager fileManager = new FileManager(context);
                fileManager.extractAssets(true /* force overwrite */);
                Logger.i(TAG, "Asset extraction completed after update");
            } catch (Exception e) {
                Logger.e(TAG, "Asset extraction failed after update: " + e.getMessage(), e);
            }

            // Signal service to restart with updated files
            Intent serviceIntent = new Intent(context, NetHunterService.class);
            serviceIntent.setAction(NetHunterService.ACTION_RESTART);
            try {
                ContextCompat.startForegroundService(context, serviceIntent);
            } catch (Exception e) {
                Logger.e(TAG, "Failed to restart service after update: " + e.getMessage(), e);
            }
        }, "UpdateReceiver-worker").start();
    }
}
