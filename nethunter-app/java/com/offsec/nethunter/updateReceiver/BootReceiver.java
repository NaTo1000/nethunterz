package com.offsec.nethunter.updateReceiver;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.preference.PreferenceManager;

import androidx.core.content.ContextCompat;

import com.offsec.nethunter.service.NetHunterService;
import com.offsec.nethunter.utils.Logger;

/**
 * {@link BroadcastReceiver} that listens for {@link Intent#ACTION_BOOT_COMPLETED}
 * (and HTC's {@code QUICKBOOT_POWERON} equivalent) and optionally re-starts the
 * {@link NetHunterService} if the user has enabled the "start on boot" preference.
 *
 * <p>Declared in {@code AndroidManifest.xml} with the {@code RECEIVE_BOOT_COMPLETED}
 * permission and priority 999 to run before most other receivers.
 */
public class BootReceiver extends BroadcastReceiver {

    private static final String TAG = "BootReceiver";

    /** SharedPreferences key that controls auto-start on boot. */
    public static final String PREF_START_ON_BOOT = "pref_start_on_boot";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
                && !"android.intent.action.QUICKBOOT_POWERON".equals(action)) {
            return;
        }

        Logger.i(TAG, "Boot completed received");

        SharedPreferences prefs = PreferenceManager.getDefaultSharedPreferences(context);
        boolean startOnBoot = prefs.getBoolean(PREF_START_ON_BOOT, false);

        if (startOnBoot) {
            Logger.i(TAG, "Auto-start on boot is enabled – starting NetHunterService");
            Intent serviceIntent = new Intent(context, NetHunterService.class);
            serviceIntent.setAction(NetHunterService.ACTION_START);
            try {
                ContextCompat.startForegroundService(context, serviceIntent);
            } catch (Exception e) {
                Logger.e(TAG, "Failed to start service at boot: " + e.getMessage(), e);
            }
        } else {
            Logger.d(TAG, "Auto-start on boot is disabled – skipping service start");
        }
    }
}
