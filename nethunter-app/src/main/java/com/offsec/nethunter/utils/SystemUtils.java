package com.offsec.nethunter.utils;

import android.content.Context;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.NetworkInfo;
import android.os.Build;
import android.util.Log;

/**
 * SystemUtils - General-purpose system utility methods for the NetHunterZ application.
 *
 * <p>Provides static helper methods for common Android system queries such as
 * checking package availability, querying the Android version, and testing
 * network connectivity.</p>
 */
public final class SystemUtils {

    private static final String TAG = "SystemUtils";

    /** Prevent instantiation of this utility class. */
    private SystemUtils() {}

    // -------------------------------------------------------------------------
    // Package management
    // -------------------------------------------------------------------------

    /**
     * Checks whether a package with the given name is installed on the device.
     *
     * @param context     the application context
     * @param packageName the fully-qualified package name to look up (e.g., {@code "com.example.app"})
     * @return {@code true} if the package is installed, {@code false} otherwise
     */
    public static boolean isPackageInstalled(Context context, String packageName) {
        if (context == null || packageName == null || packageName.isEmpty()) return false;
        try {
            context.getPackageManager().getPackageInfo(packageName, 0);
            return true;
        } catch (PackageManager.NameNotFoundException e) {
            Log.d(TAG, "Package not installed: " + packageName);
            return false;
        }
    }

    // -------------------------------------------------------------------------
    // Android version helpers
    // -------------------------------------------------------------------------

    /**
     * Returns the current Android OS version as a human-readable string.
     *
     * <p>Example: {@code "Android 13 (API 33)"}</p>
     *
     * @return formatted Android version string
     */
    public static String getAndroidVersion() {
        return String.format("Android %s (API %d)",
            Build.VERSION.RELEASE,
            Build.VERSION.SDK_INT);
    }

    /**
     * Returns the device's Android API level.
     *
     * @return API level integer (e.g., 33 for Android 13)
     */
    public static int getApiLevel() {
        return Build.VERSION.SDK_INT;
    }

    /**
     * Returns the device's manufacturer and model string.
     *
     * <p>Example: {@code "samsung SM-G991B"}</p>
     *
     * @return manufacturer + model string
     */
    public static String getDeviceModel() {
        return Build.MANUFACTURER + " " + Build.MODEL;
    }

    // -------------------------------------------------------------------------
    // Network connectivity
    // -------------------------------------------------------------------------

    /**
     * Checks whether the device currently has an active network connection.
     *
     * <p>Uses {@link NetworkCapabilities} on Android 10+ and falls back to the
     * deprecated {@link NetworkInfo} API on older versions.</p>
     *
     * @param context the application context
     * @return {@code true} if a network connection is available and validated
     */
    @SuppressWarnings("deprecation")
    public static boolean isNetworkAvailable(Context context) {
        if (context == null) return false;

        ConnectivityManager cm =
            (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return false;

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            NetworkCapabilities capabilities =
                cm.getNetworkCapabilities(cm.getActiveNetwork());
            if (capabilities == null) return false;
            return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                && capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
        } else {
            NetworkInfo activeNetwork = cm.getActiveNetworkInfo();
            return activeNetwork != null && activeNetwork.isConnected();
        }
    }

    /**
     * Checks whether the active network is a Wi-Fi connection.
     *
     * @param context the application context
     * @return {@code true} if connected via Wi-Fi
     */
    @SuppressWarnings("deprecation")
    public static boolean isWifiConnected(Context context) {
        if (context == null) return false;

        ConnectivityManager cm =
            (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return false;

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            NetworkCapabilities caps = cm.getNetworkCapabilities(cm.getActiveNetwork());
            return caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI);
        } else {
            NetworkInfo netInfo = cm.getActiveNetworkInfo();
            return netInfo != null
                && netInfo.isConnected()
                && netInfo.getType() == ConnectivityManager.TYPE_WIFI;
        }
    }
}
