package com.offsec.nethunter.cloud;

import android.content.Context;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;

/**
 * Integrates with AWS S3 and Google Cloud Storage for firmware file management.
 * Uses pre-signed URLs or direct REST API calls via OkHttp.
 */
public class CloudStorageManager {

    private static final String TAG = "CloudStorageManager";

    private static final int    CONNECT_TIMEOUT_SEC = 30;
    private static final int    READ_TIMEOUT_SEC    = 120;
    private static final int    WRITE_TIMEOUT_SEC   = 120;
    private static final String USER_AGENT          = "NetHunter-Android/1.0";

    private final Context context;
    private final OkHttpClient httpClient;
    private String s3BaseUrl;
    private String gcsBaseUrl;
    private String apiKey;

    public interface TransferListener {
        void onProgress(long bytesTransferred, long totalBytes);
        void onSuccess(String url);
        void onFailure(String error);
    }

    public CloudStorageManager(Context context) {
        this.context = context;
        this.httpClient = new OkHttpClient.Builder()
            .connectTimeout(CONNECT_TIMEOUT_SEC, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SEC, TimeUnit.SECONDS)
            .writeTimeout(WRITE_TIMEOUT_SEC, TimeUnit.SECONDS)
            .addInterceptor(chain -> {
                Request req = chain.request().newBuilder()
                    .header("User-Agent", USER_AGENT)
                    .build();
                return chain.proceed(req);
            })
            .build();
    }

    /**
     * Configure S3 endpoint and credentials.
     */
    public void configureS3(String bucketUrl, String apiKey) {
        this.s3BaseUrl = bucketUrl.endsWith("/") ? bucketUrl : bucketUrl + "/";
        this.apiKey    = apiKey;
        Log.d(TAG, "S3 configured: " + s3BaseUrl);
    }

    /**
     * Configure GCS endpoint.
     */
    public void configureGCS(String bucketUrl, String apiKey) {
        this.gcsBaseUrl = bucketUrl.endsWith("/") ? bucketUrl : bucketUrl + "/";
        if (this.apiKey == null) this.apiKey = apiKey;
        Log.d(TAG, "GCS configured: " + gcsBaseUrl);
    }

    /**
     * Download the latest firmware from cloud storage.
     * @param version   Firmware version string (e.g., "1.2.3" or "latest")
     * @param destFile  Destination file path
     * @param listener  Progress listener
     */
    public void downloadFirmware(String version, File destFile, TransferListener listener) {
        String baseUrl = s3BaseUrl != null ? s3BaseUrl : gcsBaseUrl;
        if (baseUrl == null) {
            if (listener != null) listener.onFailure("No cloud storage configured");
            return;
        }

        String url = baseUrl + "firmware/" + version + "/flipper_firmware.bin";
        Log.i(TAG, "Downloading firmware from: " + url);

        Request request = new Request.Builder()
            .url(url)
            .get()
            .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                Log.e(TAG, "Download failed", e);
                if (listener != null) listener.onFailure(e.getMessage());
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (!response.isSuccessful()) {
                    if (listener != null) listener.onFailure("HTTP " + response.code());
                    return;
                }
                try (ResponseBody body = response.body()) {
                    if (body == null) {
                        if (listener != null) listener.onFailure("Empty response body");
                        return;
                    }

                    long totalBytes = body.contentLength();
                    long transferred = 0;
                    byte[] buffer = new byte[8192];

                    destFile.getParentFile().mkdirs();
                    try (FileOutputStream fos = new FileOutputStream(destFile);
                         InputStream is = body.byteStream()) {
                        int read;
                        while ((read = is.read(buffer)) != -1) {
                            fos.write(buffer, 0, read);
                            transferred += read;
                            if (listener != null && totalBytes > 0) {
                                listener.onProgress(transferred, totalBytes);
                            }
                        }
                    }

                    Log.i(TAG, "Firmware downloaded: " + destFile.getAbsolutePath()
                        + " (" + transferred + " bytes)");
                    if (listener != null) listener.onSuccess(destFile.getAbsolutePath());
                }
            }
        });
    }

    /**
     * Upload a file to cloud storage.
     */
    public void uploadFile(File file, String remotePath, TransferListener listener) {
        String baseUrl = s3BaseUrl != null ? s3BaseUrl : gcsBaseUrl;
        if (baseUrl == null) {
            if (listener != null) listener.onFailure("No cloud storage configured");
            return;
        }

        if (!file.exists()) {
            if (listener != null) listener.onFailure("File not found: " + file.getAbsolutePath());
            return;
        }

        String url = baseUrl + remotePath;
        Log.i(TAG, "Uploading to: " + url);

        RequestBody fileBody = RequestBody.create(file, MediaType.parse("application/octet-stream"));
        RequestBody multipart = new MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", file.getName(), fileBody)
            .build();

        Request.Builder reqBuilder = new Request.Builder()
            .url(url)
            .put(RequestBody.create(file, MediaType.parse("application/octet-stream")));

        if (apiKey != null && !apiKey.isEmpty()) {
            reqBuilder.header("Authorization", "Bearer " + apiKey);
        }

        httpClient.newCall(reqBuilder.build()).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                Log.e(TAG, "Upload failed", e);
                if (listener != null) listener.onFailure(e.getMessage());
            }

            @Override
            public void onResponse(Call call, Response response) {
                if (response.isSuccessful()) {
                    Log.i(TAG, "Upload successful: " + url);
                    if (listener != null) listener.onSuccess(url);
                } else {
                    if (listener != null) listener.onFailure("HTTP " + response.code());
                }
                response.close();
            }
        });
    }

    /**
     * Fetch firmware manifest JSON from cloud.
     */
    public String fetchFirmwareManifest(String channel) throws IOException {
        String baseUrl = s3BaseUrl != null ? s3BaseUrl : gcsBaseUrl;
        if (baseUrl == null) throw new IOException("No cloud storage configured");

        String url = baseUrl + "manifest/" + channel + ".json";
        Request request = new Request.Builder().url(url).get().build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("HTTP " + response.code() + " fetching manifest");
            }
            ResponseBody body = response.body();
            return body != null ? body.string() : "{}";
        }
    }

    public void shutdown() {
        httpClient.dispatcher().executorService().shutdown();
        httpClient.connectionPool().evictAll();
    }
}
