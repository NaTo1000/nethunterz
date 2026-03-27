package com.offsec.nethunter.cloud;

import android.content.Context;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/**
 * REST API client for the NetHunter cloud dashboard.
 * Handles firmware release queries, statistics reporting, and log uploads.
 */
public class CloudDashboardClient {

    private static final String TAG = "CloudDashboardClient";
    private static final MediaType JSON_MEDIA_TYPE =
        MediaType.parse("application/json; charset=utf-8");

    private final Context context;
    private final OkHttpClient httpClient;
    private String baseUrl;
    private String apiKey;
    private String deviceId;

    public static class FirmwareRelease {
        public final String version;
        public final String downloadUrl;
        public final String releaseNotes;
        public final long   releaseDate;
        public final String sha256;
        public final boolean isStable;

        public FirmwareRelease(String version, String downloadUrl, String releaseNotes,
                               long releaseDate, String sha256, boolean isStable) {
            this.version      = version;
            this.downloadUrl  = downloadUrl;
            this.releaseNotes = releaseNotes;
            this.releaseDate  = releaseDate;
            this.sha256       = sha256;
            this.isStable     = isStable;
        }
    }

    public CloudDashboardClient(Context context, String baseUrl, String apiKey) {
        this.context  = context;
        this.baseUrl  = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.apiKey   = apiKey;
        this.deviceId = generateDeviceId(context);

        this.httpClient = new OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build();
    }

    /**
     * Get the latest stable firmware release from the dashboard.
     */
    public FirmwareRelease getLatestRelease(String channel) throws IOException {
        String url = baseUrl + "/api/firmware/latest?channel=" + channel;
        JSONObject json = getJson(url);

        return new FirmwareRelease(
            json.optString("version", "unknown"),
            json.optString("download_url", ""),
            json.optString("release_notes", ""),
            json.optLong("release_date", 0L),
            json.optString("sha256", ""),
            json.optBoolean("is_stable", true)
        );
    }

    /**
     * Get list of available firmware releases.
     */
    public List<FirmwareRelease> getReleases(int limit) throws IOException {
        String url = baseUrl + "/api/firmware/releases?limit=" + limit;
        JSONObject response = getJson(url);
        JSONArray releases = response.optJSONArray("releases");

        List<FirmwareRelease> list = new ArrayList<>();
        if (releases != null) {
            for (int i = 0; i < releases.length(); i++) {
                JSONObject obj = releases.optJSONObject(i);
                if (obj == null) continue;
                list.add(new FirmwareRelease(
                    obj.optString("version"),
                    obj.optString("download_url"),
                    obj.optString("release_notes"),
                    obj.optLong("release_date"),
                    obj.optString("sha256"),
                    obj.optBoolean("is_stable", true)
                ));
            }
        }
        return list;
    }

    /**
     * Report device statistics to the dashboard.
     */
    public boolean reportStats(JSONObject stats) {
        try {
            stats.put("device_id", deviceId);
            stats.put("timestamp", System.currentTimeMillis());

            String url = baseUrl + "/api/device/stats";
            JSONObject result = postJson(url, stats);
            return result.optBoolean("success", false);
        } catch (Exception e) {
            Log.w(TAG, "Stats report failed: " + e.getMessage());
            return false;
        }
    }

    /**
     * Upload a log file to the dashboard.
     */
    public boolean uploadLog(String logContent, String logType) {
        try {
            JSONObject payload = new JSONObject();
            payload.put("device_id", deviceId);
            payload.put("log_type", logType);
            payload.put("content", logContent);
            payload.put("timestamp", System.currentTimeMillis());

            String url = baseUrl + "/api/device/logs";
            JSONObject result = postJson(url, payload);
            return result.optBoolean("success", false);
        } catch (Exception e) {
            Log.w(TAG, "Log upload failed: " + e.getMessage());
            return false;
        }
    }

    /**
     * Check if a specific firmware version has known security issues.
     */
    public boolean checkFirmwareSecurity(String version) throws IOException {
        String url = baseUrl + "/api/security/check?version=" + version;
        JSONObject result = getJson(url);
        return result.optBoolean("safe", true);
    }

    /**
     * Notify the dashboard of a successful update.
     */
    public boolean notifyUpdateComplete(String fromVersion, String toVersion) {
        try {
            JSONObject payload = new JSONObject();
            payload.put("device_id", deviceId);
            payload.put("from_version", fromVersion);
            payload.put("to_version", toVersion);
            payload.put("timestamp", System.currentTimeMillis());

            String url = baseUrl + "/api/firmware/update-complete";
            JSONObject result = postJson(url, payload);
            return result.optBoolean("success", false);
        } catch (Exception e) {
            Log.w(TAG, "Notify update failed: " + e.getMessage());
            return false;
        }
    }

    // --- HTTP helpers ---

    private JSONObject getJson(String url) throws IOException {
        Request request = buildRequest(url).get().build();
        try (Response response = httpClient.newCall(request).execute()) {
            String body = response.body() != null ? response.body().string() : "{}";
            if (!response.isSuccessful()) {
                throw new IOException("HTTP " + response.code() + ": " + body);
            }
            try {
                return new JSONObject(body);
            } catch (Exception e) {
                throw new IOException("Invalid JSON response: " + body);
            }
        }
    }

    private JSONObject postJson(String url, JSONObject payload) throws IOException {
        RequestBody body = RequestBody.create(payload.toString(), JSON_MEDIA_TYPE);
        Request request = buildRequest(url).post(body).build();
        try (Response response = httpClient.newCall(request).execute()) {
            String responseBody = response.body() != null ? response.body().string() : "{}";
            try {
                return new JSONObject(responseBody);
            } catch (Exception e) {
                return new JSONObject();
            }
        }
    }

    private Request.Builder buildRequest(String url) {
        Request.Builder builder = new Request.Builder().url(url);
        if (apiKey != null && !apiKey.isEmpty()) {
            builder.header("Authorization", "Bearer " + apiKey);
            builder.header("X-Device-ID", deviceId);
        }
        return builder;
    }

    private String generateDeviceId(Context ctx) {
        // Use a stable device identifier (not user-identifiable)
        try {
            String androidId = android.provider.Settings.Secure.getString(
                ctx.getContentResolver(),
                android.provider.Settings.Secure.ANDROID_ID
            );
            // Hash it to avoid raw device fingerprinting
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(("nethunter-" + androidId).getBytes());
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 8; i++) sb.append(String.format("%02x", hash[i]));
            return sb.toString();
        } catch (Exception e) {
            return "unknown-device";
        }
    }

    public void setApiKey(String apiKey) { this.apiKey = apiKey; }
    public void setBaseUrl(String url)   { this.baseUrl = url; }
    public String getDeviceId()          { return deviceId; }
}
