package com.offsec.nethunter.updateReceiver;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

import com.offsec.nethunter.service.NethunterService;

/**
 * Receives BOOT_COMPLETED broadcast and starts the NethunterService.
 */
public class BootReceiver extends BroadcastReceiver {

    private static final String TAG = "BootReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        if (action == null) return;

        Log.d(TAG, "Received broadcast: " + action);

        switch (action) {
            case Intent.ACTION_BOOT_COMPLETED:
            case "android.intent.action.QUICKBOOT_POWERON":
            case "com.htc.intent.action.QUICKBOOT_POWERON":
                startService(context);
                break;
            default:
                Log.w(TAG, "Unexpected action: " + action);
        }
    }

    private void startService(Context context) {
        try {
            Intent serviceIntent = new Intent(context, NethunterService.class);
            serviceIntent.setAction(NethunterService.ACTION_START_SERVICE);
            serviceIntent.putExtra(NethunterService.EXTRA_SOURCE, "boot_receiver");

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent);
                Log.i(TAG, "Started NethunterService as foreground service (API 26+)");
            } else {
                context.startService(serviceIntent);
                Log.i(TAG, "Started NethunterService");
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to start NethunterService from boot", e);
        }
    }
}
