package com.offsec.nethunter.updateReceiver;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

import com.offsec.nethunter.service.NethunterService;

/**
 * BootReceiver - BroadcastReceiver that automatically starts {@link NethunterService}
 * when the device completes its boot sequence.
 *
 * <p>This receiver listens for {@link Intent#ACTION_BOOT_COMPLETED} (and the
 * HTC/Samsung equivalent {@code QUICKBOOT_POWERON}) so that NetHunter services
 * are available immediately after the device is powered on without requiring the
 * user to manually open the application.</p>
 *
 * <p>Requires the {@code android.permission.RECEIVE_BOOT_COMPLETED} permission
 * to be declared in {@code AndroidManifest.xml}.</p>
 */
public class BootReceiver extends BroadcastReceiver {

    private static final String TAG = "BootReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || intent.getAction() == null) return;

        String action = intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
                && !"android.intent.action.QUICKBOOT_POWERON".equals(action)) {
            Log.d(TAG, "Ignoring unrelated broadcast: " + action);
            return;
        }

        Log.i(TAG, "Boot completed – starting NethunterService");

        Intent serviceIntent = new Intent(context, NethunterService.class);
        serviceIntent.setAction(NethunterService.ACTION_START);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(serviceIntent);
        } else {
            context.startService(serviceIntent);
        }
    }
}
